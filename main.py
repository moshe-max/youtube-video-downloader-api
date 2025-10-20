#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.0 - VIDEO ONLY
- /info: Video metadata
- /download: RAW MP4 (no MIME/HTML/thumbnails)
- /health: API status
"""

import os
import re
import json
import time
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
from werkzeug.utils import secure_filename
import tempfile
import shutil

app = Flask(__name__)
CORS(app)  # Allow Google Apps Script

# ================================
# 🔧 CONFIGURATION
# ================================

# Video settings
MAX_DURATION = 20 * 60  # 20 minutes
ALLOWED_RESOLUTIONS = ['360p', '480p', '720p']
DEFAULT_RESOLUTION = '360p'

# File handling
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
TEMP_DIR = tempfile.mkdtemp()

# Format selection (CRITICAL - NO THUMBNAILS!)
VIDEO_FORMATS = {
    '360p': 'bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]/best',
    '480p': 'bestvideo[height<=480]+bestaudio[ext=m4a]/best[height<=480]/best', 
    '720p': 'bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best'
}

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /info?url=<youtube_url>': 'Video metadata',
            'POST /download': 'Download video {"url": "...", "resolution": "360p"}'
        },
        'message': '🎥 YouTube Downloader API - Video Only'
    })

# ================================
# 📊 VIDEO INFO
# ================================

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'Missing url parameter'}), 400
    
    try:
        # yt-dlp options for info only
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  # Get full info
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Basic video info
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),  # For Apps Script
                'thumbnail': info.get('thumbnail') or f"https://img.youtube.com/vi/{info.get('id')}/maxresdefault.jpg",
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date'),
                'formats': len(info.get('formats', [])),
                'can_download': True
            }
            
            # Duration check
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long ({result["length"]}s > {MAX_DURATION}s)'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': f'Failed to get info: {str(e)}'
        }), 500

# ================================
# ⬇️ VIDEO DOWNLOAD (RAW MP4)
# ================================

@app.route('/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data'}), 400
        
        url = data.get('url')
        resolution = data.get('resolution', DEFAULT_RESOLUTION)
        
        if not url:
            return jsonify({'success': False, 'error': 'Missing url'}), 400
        
        if resolution not in ALLOWED_RESOLUTIONS:
            resolution = DEFAULT_RESOLUTION
        
        # CRITICAL: Video-only format (NO thumbnails/subs!)
        format_selector = VIDEO_FORMATS.get(resolution, VIDEO_FORMATS[DEFAULT_RESOLUTION])
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': '%(title)s.%(ext)s',  # Simple filename
            'merge_output_format': 'mp4',    # Always MP4
            'quiet': True,
            'no_warnings': True,
            
            # 🔥 DISABLE ALL THUMBNAILS/SLIDESHOWS
            'writethumbnail': False,
            'write_all_thumbnails': False,
            'embed_thumbnail': False,
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            
            # No playlists
            'noplaylist': True,
            
            # Paths
            'paths': {'home': TEMP_DIR},
        }
        
        print(f"⬇️ Downloading: {url} at {resolution}...")
        print(f"📐 Format: {format_selector}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(url, download=True)
            
            # Get filename
            filename = ydl.prepare_filename(info)
            
            # Find actual downloaded file (handle merging)
            video_file = None
            for ext in ['.mp4', '.mkv', '.webm']:
                test_file = filename.rsplit('.', 1)[0] + ext
                if os.path.exists(test_file):
                    video_file = test_file
                    break
            
            if not video_file or not os.path.exists(video_file):
                return jsonify({
                    'success': False, 
                    'error': f'Video not found after download: {video_file}'
                }), 500
            
            # Check size
            file_size = os.path.getsize(video_file)
            if file_size > MAX_FILE_SIZE:
                os.remove(video_file)
                return jsonify({
                    'success': False,
                    'error': f'File too large: {file_size / (1024*1024):.1f}MB > {MAX_FILE_SIZE / (1024*1024)}MB'
                }), 413
            
            # Send RAW MP4
            print(f"✅ Video ready: {video_file} ({file_size / (1024*1024):.1f}MB)")
            
            return send_file(
                video_file,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=f"{info.get('title', 'video')[:100]}.mp4",
                conditional=True
            )
            
    except yt_dlp.DownloadError as e:
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

# ================================
# 🧹 CLEANUP
# ================================

@app.teardown_appcontext
def cleanup_files(exception):
    """Clean temp files on request end"""
    if os.path.exists(TEMP_DIR):
        try:
            shutil.rmtree(TEMP_DIR)
        except:
            pass

# ================================
# 🚀 MAIN
# ================================

if __name__ == '__main__':
    print("🎥 Starting YouTube Downloader API v2.0...")
    print(f"📁 Temp dir: {TEMP_DIR}")
    print("✅ Video-only mode (no thumbnails/HTML)")
    print("🔗 Endpoints: /health, /info, /download")
    
    # Create temp dir if needed
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Run Flask
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
