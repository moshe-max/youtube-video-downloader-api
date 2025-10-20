#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.4 - DYNAMIC MP4 SELECTION
- Auto-detects BEST available MP4 format
- Lists ALL formats for debug
- Fallback to any video if no MP4
"""

import os
import re
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import shutil
import glob

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 CONFIGURATION
# ================================

MAX_DURATION = 20 * 60
ALLOWED_RESOLUTIONS = ['360p', '480p', '720p']
DEFAULT_RESOLUTION = '720p'  # Start with highest
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

# ================================
# 🛠️ SMART FORMAT SELECTOR
# ================================

def get_best_format(url, target_resolution):
    """Dynamically find best MP4 format"""
    print(f"🔍 Finding best format for {target_resolution}...")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # Get all MP4 formats
        mp4_formats = []
        for f in info.get('formats', []):
            if f.get('ext') == 'mp4' and f.get('height') and f.get('vcodec') != 'none':
                mp4_formats.append({
                    'format_id': f.get('format_id'),
                    'height': f.get('height'),
                    'filesize': f.get('filesize', 0),
                    'fps': f.get('fps', 0),
                    'format_note': f.get('format_note', ''),
                    'vcodec': f.get('vcodec', '')
                })
        
        print(f"📊 Found {len(mp4_formats)} MP4 formats:")
        for fmt in sorted(mp4_formats, key=lambda x: x['height'], reverse=True)[:10]:
            size = fmt['filesize'] / (1024*1024) if fmt['filesize'] else '?'
            print(f"  {fmt['format_id']}: {fmt['height']}p ({size:.1f}MB, {fmt['fps']}fps)")
        
        if not mp4_formats:
            print("❌ No MP4 formats found - trying any video")
            # Fallback: best video regardless of container
            return 'best[height<=720]/best'
        
        # Find best MP4 <= target resolution
        target_height = int(target_resolution[:-1])
        best_format = None
        best_height = 0
        
        for fmt in mp4_formats:
            height = fmt['height']
            if height <= target_height and height > best_height:
                best_format = fmt['format_id']
                best_height = height
        
        # If no exact match, take highest available
        if not best_format:
            best_format = max(mp4_formats, key=lambda x: x['height'])['format_id']
            best_height = max(mp4_formats, key=lambda x: x['height'])['height']
        
        format_selector = f"{best_format}/best[ext=mp4]"
        print(f"✅ Selected: {best_format} ({best_height}p)")
        
        return format_selector, {
            'selected_format_id': best_format,
            'selected_height': best_height,
            'total_mp4_formats': len(mp4_formats)
        }

# ================================
# 🛠️ FILE FINDER
# ================================

def find_video_file(temp_dir):
    """Find largest video file"""
    if not os.path.exists(temp_dir):
        return None
    
    all_files = os.listdir(temp_dir)
    video_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.webm'])]
    
    print(f"📁 Found video files: {video_files}")
    
    if not video_files:
        # Show all files for debug
        file_sizes = {}
        for f in all_files:
            path = os.path.join(temp_dir, f)
            if os.path.isfile(path):
                size = os.path.getsize(path) / (1024*1024)
                file_sizes[f] = f"{size:.1f}MB"
        print(f"❌ No video files! All files: {file_sizes}")
        return None
    
    # Return largest video file
    largest_file = max(video_files, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
    filepath = os.path.join(temp_dir, largest_file)
    size_mb = os.path.getsize(filepath) / (1024*1024)
    print(f"✅ Largest video: {largest_file} ({size_mb:.1f}MB)")
    return filepath

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.4',
        'message': '🎥 Dynamic MP4 Selector API'
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
            
            # Count MP4 formats
            mp4_count = sum(1 for f in info.get('formats', []) if f.get('ext') == 'mp4')
            
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'mp4_formats': mp4_count,
                'can_download': True
            }
            
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Info failed: {str(e)}'}), 500

# ================================
# ⬇️ DYNAMIC DOWNLOAD
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
        
        print(f"\n🎬 DYNAMIC DOWNLOAD START")
        print(f"🔗 URL: {url}")
        print(f"📐 Target: {resolution}")
        
        # Clear temp dir
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # 🔥 DYNAMIC FORMAT SELECTION
        format_selector, format_info = get_best_format(url, resolution)
        print(f"📐 Using format: {format_selector}")
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': '%(title)s.%(ext)s',
            
            # Debug
            'quiet': False,
            'no_warnings': False,
            
            # NO EXTRAS
            'writethumbnail': False,
            'write_all_thumbnails': False,
            'embed_thumbnail': False,
            'embed_metadata': False,
            'noplaylist': True,
            
            # Paths
            'paths': {'home': TEMP_DIR},
        }
        
        print("⬇️ Starting download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            print(f"✅ Download complete: {info.get('title')}")
        
        # Find video file
        video_file = find_video_file(TEMP_DIR)
        if not video_file:
            files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
            return jsonify({
                'success': False,
                'error': f'No video file found. Files: {files}'
            }), 500
        
        file_size = os.path.getsize(video_file)
        if file_size > MAX_FILE_SIZE:
            os.remove(video_file)
            return jsonify({'success': False, 'error': f'File too large'}), 413
        
        # Safe filename
        title = info.get('title', 'video')[:80]
        safe_filename = re.sub(r'[^\w\s-]', '_', title) + '.mp4'
        print(f"📤 Sending: {safe_filename} ({file_size/(1024*1024):.1f}MB)")
        
        response = send_file(
            video_file,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=safe_filename,
            conditional=True
        )
        
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(video_file):
                    os.remove(video_file)
                shutil.rmtree(TEMP_DIR, ignore_errors=True)
            except:
                pass
        
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"🎥 Starting Dynamic MP4 API v2.4")
    print(f"🌐 {host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
