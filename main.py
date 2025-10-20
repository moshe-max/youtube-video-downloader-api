#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.2 - ROBUST FILE DETECTION
- Finds ALL downloaded files in temp dir
- Handles yt-dlp naming variations
- Detailed debug logging
"""

import os
import re
import json
import time
import sys
import glob
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import tempfile
import shutil
import threading
import signal

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 CONFIGURATION
# ================================

MAX_DURATION = 20 * 60
ALLOWED_RESOLUTIONS = ['360p', '480p', '720p']
DEFAULT_RESOLUTION = '360p'
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

VIDEO_FORMATS = {
    '360p': 'bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]/best[ext=mp4]',
    '480p': 'bestvideo[height<=480]+bestaudio[ext=m4a]/best[height<=480]/best[ext=mp4]',
    '720p': 'bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best[ext=mp4]'
}

# ================================
# 🛠️ FILE FINDER UTILITIES
# ================================

def find_video_file(temp_dir, info):
    """Find ANY video file in temp dir - ROBUST"""
    print(f"🔍 Searching for video in: {temp_dir}")
    
    # List ALL files before filtering
    all_files = os.listdir(temp_dir)
    print(f"📁 ALL FILES ({len(all_files)}): {all_files[:10]}{'...' if len(all_files) > 10 else ''}")
    
    # Possible video extensions
    video_exts = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.f137.mp4', '.f136.mp4']
    
    # 1. Look for files matching video title
    title = info.get('title', '').replace('/', '_').replace('\\', '_')[:100]
    print(f"🎬 Title pattern: {title}")
    
    for ext in video_exts:
        pattern = os.path.join(temp_dir, f"*{title}*{ext}")
        matches = glob.glob(pattern)
        if matches:
            print(f"✅ TITLE MATCH: {matches[0]}")
            return matches[0]
    
    # 2. Look for ANY video file > 1MB
    for filename in all_files:
        filepath = os.path.join(temp_dir, filename)
        if os.path.isfile(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > 1 and any(filename.lower().endswith(ext) for ext in video_exts):
                print(f"✅ LARGE VIDEO: {filename} ({size_mb:.1f}MB)")
                return filepath
    
    # 3. Look for ANY file > 1MB (last resort)
    large_files = []
    for filename in all_files:
        filepath = os.path.join(temp_dir, filename)
        if os.path.isfile(filepath):
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > 1:
                large_files.append((filename, size_mb))
    
    if large_files:
        large_files.sort(key=lambda x: x[1], reverse=True)
        print(f"⚠️ Largest files: {large_files[:3]}")
        return os.path.join(temp_dir, large_files[0][0])
    
    print(f"❌ NO VIDEO FILES FOUND")
    return None

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.2',
        'temp_dir': TEMP_DIR,
        'temp_dir_exists': os.path.exists(TEMP_DIR),
        'message': '🎥 YouTube Downloader API - Robust File Detection'
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
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),
                'thumbnail': info.get('thumbnail') or f"https://img.youtube.com/vi/{info.get('id')}/maxresdefault.jpg",
                'formats': len(info.get('formats', [])),
                'can_download': True
            }
            
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long ({result["length"]}s)'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get info: {str(e)}'}), 500

# ================================
# ⬇️ VIDEO DOWNLOAD
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
        
        format_selector = VIDEO_FORMATS.get(resolution, VIDEO_FORMATS[DEFAULT_RESOLUTION])
        
        print(f"\n🎬 DOWNLOAD START")
        print(f"🔗 URL: {url}")
        print(f"📐 Resolution: {resolution}")
        print(f"📐 Format: {format_selector}")
        print(f"📁 Temp dir: {TEMP_DIR}")
        
        # Clear temp dir first
        if os.path.exists(TEMP_DIR):
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except:
                    pass
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': '%(title)s.%(ext)s',  # Simple: "Title.mp4"
            'merge_output_format': 'mp4',
            'quiet': False,  # Enable yt-dlp logs for debug
            'no_warnings': False,
            
            # NO EXTRAS
            'writethumbnail': False,
            'write_all_thumbnails': False,
            'embed_thumbnail': False,
            'embed_metadata': False,
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'noplaylist': True,
            
            # Paths
            'paths': {'home': TEMP_DIR},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("⬇️ yt-dlp downloading...")
            info = ydl.extract_info(url, download=True)
            print(f"✅ Download complete: {info.get('title', 'Unknown')}")
            
            # Find video file (ROBUST)
            video_file = find_video_file(TEMP_DIR, info)
            
            if not video_file:
                # Debug: list ALL files
                files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
                sizes = [(f, os.path.getsize(os.path.join(TEMP_DIR, f)) / (1024*1024)) for f in files if os.path.isfile(os.path.join(TEMP_DIR, f))]
                sizes.sort(key=lambda x: x[1], reverse=True)
                
                debug_info = {
                    'files': {f: f"{s:.1f}MB" for f, s in sizes[:10]},
                    'total_files': len(files),
                    'temp_dir': TEMP_DIR
                }
                
                print(f"❌ DEBUG INFO: {json.dumps(debug_info, indent=2)}")
                return jsonify({
                    'success': False,
                    'error': f'No video file found. Debug: {json.dumps(debug_info)}'
                }), 500
            
            file_size = os.path.getsize(video_file)
            print(f"📁 Video found: {os.path.basename(video_file)} ({file_size / (1024*1024):.1f}MB)")
            
            if file_size > MAX_FILE_SIZE:
                os.remove(video_file)
                return jsonify({
                    'success': False,
                    'error': f'File too large: {file_size / (1024*1024):.1f}MB'
                }), 413
            
            # Send video
            safe_filename = re.sub(r'[^\w\s-]', '_', info.get('title', 'video'))[:100] + '.mp4'
            print(f"📤 Sending: {safe_filename}")
            
            response = send_file(
                video_file,
                mimetype='video/mp4',
                as_attachment=True,
                download_name=safe_filename,
                conditional=True
            )
            
            # Cleanup after sending
            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(video_file):
                        os.remove(video_file)
                        print(f"🧹 Cleaned: {video_file}")
                    # Clean entire temp dir
                    if os.path.exists(TEMP_DIR):
                        for f in os.listdir(TEMP_DIR):
                            os.remove(os.path.join(TEMP_DIR, f))
                except Exception as e:
                    print(f"⚠️ Cleanup failed: {e}")
            
            return response
            
    except yt_dlp.DownloadError as e:
        print(f"❌ yt-dlp error: {str(e)}")
        return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 400
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

# ================================
# 🚀 SERVER
# ================================

def run_server():
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"🎥 Starting YouTube Downloader API v2.2")
    print(f"🌐 {host}:{port}")
    print(f"📁 Temp: {TEMP_DIR}")
    print("✅ Robust file detection")
    
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    app.run(host=host, port=port, debug=False, threaded=True)

if __name__ == '__main__':
    if 'PORT' in os.environ:
        run_server()
    else:
        app.run(debug=True)
