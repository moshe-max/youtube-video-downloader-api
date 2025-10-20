#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v3.2 - RENDER OPTIMIZED
- Forces SINGLE progressive MP4 (NO DASH fragments)
- 30s timeout protection
- File validation
- Streaming response
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import shutil
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# ⚡ RENDER-OPTIMIZED YTDL CONFIG
# ================================

YTDL_OPTS = {
    # 🎯 FORCE SINGLE MP4 FILE - NO DASH FRAGMENTS
    'format': 'best[ext=mp4][vcodec!~*vp9][height<=480]/best[ext=mp4][height<=360]/worst[ext=mp4]/best',
    
    # 🚫 DISABLE FRAGMENT DOWNLOADS
    'noplaylist': True,
    'no_merge': True,  # CRITICAL: No DASH merging
    'merge_output_format': None,
    
    # ⏱️ TIMEOUT PROTECTION
    'socket_timeout': 30,
    'fragment_retries': 0,  # NO fragment retries
    'retries': 2,
    
    # 💾 MINIMAL OUTPUT
    'outtmpl': '%(title).100s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': False,
    
    # 🚫 NO EXTRA FILES
    'writeinfojson': False,
    'writethumbnail': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
}

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '3.2',
        'message': '🎥 Render-optimized single MP4 downloader'
    })

# ================================
# 📊 VIDEO INFO
# ================================

@app.route('/info', methods=['GET'])
def info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = [f for f in info.get('formats', []) 
                      if f.get('ext') == 'mp4' and f.get('vcodec') != 'none']
            
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'mp4_formats': len(formats),
                'thumbnail': info.get('thumbnail'),
                'uploader': info.get('uploader')
            })
    except Exception as e:
        logger.error(f"Info error: {e}")
        return jsonify({'error': str(e)}), 400

# ================================
# ⬇️ DOWNLOAD ENDPOINT
# ================================

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url') if data else request.form.get('url')
    quality = (data.get('quality') if data else request.form.get('quality', '360p'))
    
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    
    logger.info(f"Starting download: {url} ({quality})")
    
    # Quality selector - PRIORITIZE PROGRESSIVE MP4
    quality_map = {
        '720p': 'best[ext=mp4][vcodec!~*vp9][height<=720]/best[ext=mp4][height<=720]',
        '480p': 'best[ext=mp4][vcodec!~*vp9][height<=480]/best[ext=mp4][height<=480]',
        '360p': 'best[ext=mp4][vcodec!~*vp9][height<=360]/best[ext=mp4][height<=360]'
    }
    
    fmt = quality_map.get(quality, quality_map['360p'])
    opts = YTDL_OPTS.copy()
    opts['format'] = fmt
    
    temp_dir = None
    temp_file = None
    
    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='yt_')
        opts['outtmpl'] = os.path.join(temp_dir, '%(title).100s.%(ext)s')
        
        logger.info(f"Temp dir: {temp_dir}")
        
        # Download with error handling
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        # Find downloaded file
        files = glob.glob(os.path.join(temp_dir, '*.mp4'))
        if not files:
            files = glob.glob(os.path.join(temp_dir, '*'))  # Fallback
        
        if not files:
            return jsonify({'error': 'No video file found'}), 500
        
        temp_file = files[0]
        file_size = os.path.getsize(temp_file)
        
        logger.info(f"Downloaded: {temp_file} ({file_size} bytes)")
        
        # VALIDATE FILE - MUST BE > 50KB
        if file_size < 51200:  # 50KB minimum
            logger.error(f"File too small: {file_size} bytes")
            return jsonify({'error': f'Invalid video file ({file_size} bytes)'}), 400
        
        # VALIDATE MP4
        if not is_valid_mp4(temp_file):
            logger.error("Invalid MP4 format")
            return jsonify({'error': 'Invalid MP4 file'}), 400
        
        # Stream file
        def generate():
            try:
                with open(temp_file, 'rb') as f:
                    while True:
                        chunk = f.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        yield chunk
            finally:
                cleanup(temp_dir)
        
        logger.info(f"Streaming {file_size} bytes")
        
        return Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{os.path.basename(temp_file)}"',
                'Content-Length': str(file_size),
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache, no-store',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
        
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        cleanup(temp_dir)
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

def is_valid_mp4(file_path):
    """Basic MP4 validation"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
            return header == b'ftyp' or header == b'moov' or header == b'mdat'
    except:
        return False

def cleanup(temp_dir):
    """Safe cleanup"""
    try:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

# ================================
# 🧹 ROOT + CATCH-ALL
# ================================

@app.route('/', methods=['GET'])
def root():
    return jsonify({'message': '🎥 YouTube Downloader API v3.2', 'endpoints': ['/health', '/info', '/download']})

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ================================
# 🚀 RENDER PRODUCTION SERVER
# ================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
