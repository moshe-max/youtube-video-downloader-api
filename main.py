#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.3 - FORCE MP4 OUTPUT
- Explicit MP4 format selection
- No HTML/MHTML fallbacks
- Detailed yt-dlp format debug
"""

import os
import re
import json
import glob
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import shutil

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 CONFIGURATION - MP4 ONLY
# ================================

MAX_DURATION = 20 * 60
ALLOWED_RESOLUTIONS = ['360p', '480p', '720p']
DEFAULT_RESOLUTION = '360p'
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

# 🔥 MP4-SPECIFIC FORMATS (NO HTML FALLBACKS)
VIDEO_FORMATS = {
    '360p': 'best[ext=mp4][height<=360]/worst[ext=mp4][height<=360]',
    '480p': 'best[ext=mp4][height<=480]/worst[ext=mp4][height<=480]',
    '720p': 'best[ext=mp4][height<=720]/worst[ext=mp4][height<=720]'
}

# ================================
# 🛠️ ROBUST FILE FINDER
# ================================

def find_video_file(temp_dir, info):
    """Find MP4 files ONLY"""
    print(f"🔍 Searching MP4 in: {temp_dir}")
    
    all_files = os.listdir(temp_dir)
    print(f"📁 ALL FILES ({len(all_files)}): {all_files}")
    
    # MP4 files only
    mp4_files = [f for f in all_files if f.lower().endswith('.mp4')]
    print(f"🎬 MP4 FILES: {mp4_files}")
    
    if mp4_files:
        # Pick largest MP4
        largest = max(mp4_files, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
        filepath = os.path.join(temp_dir, largest)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"✅ LARGEST MP4: {largest} ({size_mb:.1f}MB)")
        return filepath
    
    # Debug: show all file sizes
    file_info = {}
    for f in all_files:
        path = os.path.join(temp_dir, f)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            file_info[f] = f"{size_mb:.1f}MB"
    
    print(f"❌ NO MP4 FILES! All files: {file_info}")
    return None

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.3',
        'temp_dir': TEMP_DIR,
        'formats': VIDEO_FORMATS,
        'message': '🎥 MP4-Only YouTube Downloader'
    })

# ================================
# 📊 VIDEO INFO + FORMATS
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
            
            # List available MP4 formats for debug
            mp4_formats = []
            for f in info.get('formats', []):
                if f.get('ext') == 'mp4' and f.get('height'):
                    mp4_formats.append({
                        'format_id': f.get('format_id'),
                        'height': f.get('height'),
                        'filesize': f.get('filesize'),
                        'fps': f.get('fps')
                    })
            
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'mp4_formats_available': len(mp4_formats),
                'sample_formats': mp4_formats[:5],  # First 5 MP4 formats
                'can_download': True
            }
            
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Info failed: {str(e)}'}), 500

# ================================
# ⬇️ MP4-ONLY DOWNLOAD
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
        
        print(f"\n🎬 MP4 DOWNLOAD START")
        print(f"🔗 URL: {url}")
        print(f"📐 Resolution: {resolution}")
        print(f"📐 MP4 Format: {format_selector}")
        
        # Clear temp dir
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # MP4-ONLY yt-dlp options
        ydl_opts = {
            # 🔥 FORCE MP4 - NO FALLBACKS
            'format': format_selector,
            'outtmpl': '%(title)s [%(height)s].%(ext)s',  # "Title [360].mp4"
            
            # MP4 settings
            'merge_output_format': None,  # Don't merge - use MP4 only
            'format_sort': ['ext:mp4', 'res:720', 'size'],  # Prefer MP4
            
            # Debug logging
            'quiet': False,
            'no_warnings': False,
            'verbose': True,
            
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
        
        print(f"⬇️ Starting yt-dlp with format: {format_selector}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Test format availability first
            try:
                info = ydl.extract_info(url, download=False)
                print(f"✅ Info extracted: {info.get('title')}")
                
                # Check if MP4 formats exist
                mp4_count = sum(1 for f in info.get('formats', []) if f.get('ext') == 'mp4')
                print(f"📊 Available MP4 formats: {mp4_count}")
                
                if mp4_count == 0:
                    return jsonify({
                        'success': False,
                        'error': 'No MP4 formats available for this video'
                    }), 400
                
                # Download
                print("⬇️ Downloading MP4...")
                info = ydl.extract_info(url, download=True)
                print(f"✅ Download complete!")
                
            except yt_dlp.DownloadError as e:
                print(f"❌ yt-dlp error: {str(e)}")
                return jsonify({'success': False, 'error': f'Download failed: {str(e)}'}), 400
        
        # Find MP4 file
        video_file = find_video_file(TEMP_DIR, info)
        
        if not video_file:
            files = os.listdir(TEMP_DIR)
            return jsonify({
                'success': False,
                'error': f'No MP4 file found. Files: {files}'
            }), 500
        
        file_size = os.path.getsize(video_file)
        if file_size > MAX_FILE_SIZE:
            os.remove(video_file)
            return jsonify({'success': False, 'error': f'File too large: {file_size/(1024*1024):.1f}MB'}), 413
        
        safe_filename = re.sub(r'[^\w\s-]', '_', info.get('title', 'video'))[:80] + f'_{resolution}.mp4'
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
                print("🧹 Cleanup complete")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")
        
        return response
        
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
    
    print(f"🎥 Starting MP4-Only API v2.3")
    print(f"🌐 {host}:{port}")
    print(f"📁 Temp: {TEMP_DIR}")
    print("✅ MP4 formats only - no HTML/MHTML")
    
    app.run(host=host, port=port, debug=False, threaded=True)
