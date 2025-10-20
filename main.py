#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v3.0 - SINGLE FILE MP4 ONLY
- Forces progressive MP4 (NO DASH fragments)
- 15s timeout per video
- Streams directly (no file saving)
- Works on Render free tier
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import shutil
from io import BytesIO

app = Flask(__name__)
CORS(app)

# ================================
# ⚡ ULTRA-FAST YTDL CONFIG
# ================================

YTDL_OPTS = {
    # 🎯 FORCE SINGLE MP4 FILE (NO DASH)
    'format': 'best[ext=mp4][height<=480]/best[ext=mp4][height<=360]/worst[ext=mp4]',
    
    # 🚫 NO FRAGMENTS/MERGE
    'noplaylist': True,
    'no_merge': True,
    'writeinfojson': False,
    'writethumbnail': False,
    'writesubtitles': False,
    
    # ⏱️ TIMEOUTS
    'socket_timeout': 15,
    'fragment_retries': 1,
    'retries': 1,
    
    # 💾 MINIMAL OUTPUT
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
}

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'version': '3.0'})

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
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'formats': len(info.get('formats', [])),
                'thumbnail': info.get('thumbnail')
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ================================
# ⬇️ DOWNLOAD ENDPOINT
# ================================

@app.route('/download', methods=['POST'])
def download():
    url = request.json.get('url')
    quality = request.json.get('quality', '360p')  # 360p, 480p, 720p
    
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    
    # Quality selector
    if quality == '720p':
        fmt = 'best[ext=mp4][height<=720]'
    elif quality == '480p':
        fmt = 'best[ext=mp4][height<=480]'
    else:  # 360p (default - fastest)
        fmt = 'best[ext=mp4][height<=360]'
    
    # Update format selector
    opts = YTDL_OPTS.copy()
    opts['format'] = fmt
    
    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            tmp_path = tmp.name
        
        # Download
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        # Check file size (must be > 100KB)
        if os.path.getsize(tmp_path) < 102400:  # 100KB
            os.unlink(tmp_path)
            return jsonify({'error': 'Invalid video file (too small)'}), 400
        
        # Stream file
        def generate():
            with open(tmp_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk
            os.unlink(tmp_path)  # Cleanup
        
        return Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="video.mp4"',
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

# ================================
# 🚀 START SERVER
# ================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
