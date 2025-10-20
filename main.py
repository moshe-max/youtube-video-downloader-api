#!/usr/bin/env python3
"""
🎥 PYTUBE DOWNLOADER API - RENDER READY
✅ Single MP4 files (no fragments)
✅ No FFmpeg needed
✅ 2s cold starts
✅ Works with your email system
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import pytube
import tempfile
import os
import logging
import glob

app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'downloader': 'pytube',
        'version': '1.0',
        'message': '🎥 Single MP4 downloader - Render ready'
    })

@app.route('/info', methods=['GET'])
def info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    
    try:
        yt = pytube.YouTube(url)
        streams = yt.streams.filter(progressive=True, file_extension='mp4')
        
        return jsonify({
            'title': yt.title,
            'duration': yt.length,
            'author': yt.author,
            'thumbnail': yt.thumbnail_url,
            'available_formats': [
                {'resolution': s.resolution, 'size_mb': round(s.filesize / (1024*1024), 1)} 
                for s in streams
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    quality = data.get('quality', '360p')
    
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
    
    try:
        logger.info(f"🎥 Downloading: {url} ({quality})")
        yt = pytube.YouTube(url)
        
        # Get progressive MP4 stream
        if quality == '720p':
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution='720p').first()
        elif quality == '480p':
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution='480p').first()
        else:
            stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution='360p').first()
        
        # Fallback to lowest quality
        if not stream:
            stream = yt.streams.filter(progressive=True, file_extension='mp4').first()
        
        if not stream:
            return jsonify({'error': 'No MP4 stream available'}), 400
        
        logger.info(f"📹 Selected: {stream.resolution} ({stream.filesize_mb:.1f}MB)")
        
        # Download to temp file
        temp_dir = tempfile.mkdtemp()
        filename = yt.title[:100].replace('/', '_').replace('\\', '_')
        temp_file = stream.download(output_path=temp_dir, filename=filename)
        
        # Validate file
        file_size = os.path.getsize(temp_file)
        if file_size < 102400:  # 100KB minimum
            return jsonify({'error': f'File too small: {file_size} bytes'}), 400
        
        # Stream response
        def generate():
            try:
                with open(temp_file, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        yield chunk
            finally:
                # Cleanup
                try:
                    os.unlink(temp_file)
                    os.rmdir(temp_dir)
                except:
                    pass
        
        return Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}.mp4"',
                'Content-Length': str(file_size),
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Download failed: {str(e)}")
        # Cleanup
        try:
            temp_dir = tempfile.gettempdir()
            for f in glob.glob(f"{temp_dir}/*.mp4"):
                os.unlink(f)
        except:
            pass
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': '🎥 YouTube Downloader API (Pytube)',
        'endpoints': {
            'health': '/health',
            'info': '/info?url=...',
            'download': '/download (POST)'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
