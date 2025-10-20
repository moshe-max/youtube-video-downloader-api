#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.6 - ANTI-BLOCK + ROBUST
- Stealth headers to bypass YouTube blocks
- Retries with delays
- Fallback formats
- MHTML rejection
"""

import os
import re
import json
import time
import random
import shutil
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import glob

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 STEALTH CONFIGURATION
# ================================

MAX_DURATION = 20 * 60
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

# Stealth user agents (rotate to avoid blocks)
STEALTH_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# ================================
# 🛡️ ANTI-BLOCK OPTIONS
# ================================

def get_stealth_ydl_opts():
    """yt-dlp options to bypass YouTube blocks"""
    return {
        # Stealth headers
        'user_agent': random.choice(STEALTH_AGENTS),
        'referer': 'https://www.youtube.com/',
        'impersonate': 'chrome110',  # Pretend to be Chrome 110
        
        # Rate limiting
        'sleep_interval': 1,
        'max_sleep_interval': 5,
        'sleep_subtitles': 3,
        
        # Retries
        'retries': 10,
        'fragment_retries': 10,
        'extractor_retries': 5,
        
        # Format preference
        'format': 'bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best',
        'merge_output_format': 'mp4',
        
        # NO MHTML/THUMBNAILS
        'writethumbnail': False,
        'write_all_thumbnails': False,
        'embed_thumbnail': False,
        'noplaylist': True,
        
        # Paths
        'outtmpl': '%(title)s.%(ext)s',
        'paths': {'home': TEMP_DIR},
        
        # Debug
        'quiet': False,
        'no_warnings': False,
    }

# ================================
# 🛠️ FILE VALIDATOR
# ================================

def is_valid_video_file(filepath):
    """Check if file is actual video (not MHTML/HTML)"""
    if not os.path.exists(filepath):
        return False
    
    # Reject MHTML/HTML
    if filepath.lower().endswith(('.mhtml', '.html')):
        print(f"❌ REJECTED MHTML: {filepath}")
        return False
    
    # Check size (videos > 1MB)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb < 1:
        print(f"❌ TOO SMALL: {os.path.basename(filepath)} ({size_mb:.1f}MB)")
        return False
    
    # Check video extensions
    valid_exts = ['.mp4', '.mkv', '.webm', '.avi', '.mov']
    if not any(filepath.lower().endswith(ext) for ext in valid_exts):
        print(f"❌ INVALID EXT: {os.path.basename(filepath)}")
        return False
    
    print(f"✅ VALID VIDEO: {os.path.basename(filepath)} ({size_mb:.1f}MB)")
    return True

def find_valid_video(temp_dir):
    """Find first valid video file"""
    if not os.path.exists(temp_dir):
        return None
    
    all_files = os.listdir(temp_dir)
    print(f"📁 Checking {len(all_files)} files...")
    
    for filename in all_files:
        filepath = os.path.join(temp_dir, filename)
        if os.path.isfile(filepath) and is_valid_video_file(filepath):
            return filepath
    
    # Debug: show all files
    debug = {}
    for f in all_files:
        path = os.path.join(temp_dir, f)
        if os.path.isfile(path):
            size = os.path.getsize(path) / (1024 * 1024)
            debug[f] = f"{size:.1f}MB"
    print(f"❌ NO VALID VIDEOS! Files: {debug}")
    return None

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.6',
        'message': '🎥 Anti-Block YouTube Downloader',
        'temp_dir': TEMP_DIR
    })

# ================================
# 📊 VIDEO INFO (STEALTH)
# ================================

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'Missing url parameter'}), 400
    
    try:
        ydl_opts = get_stealth_ydl_opts()
        ydl_opts.update({
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True  # Faster info only
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'can_download': True
            }
            
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Info failed: {str(e)}'}), 500

# ================================
# ⬇️ STEALTH DOWNLOAD
# ================================

@app.route('/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data'}), 400
        
        url = data.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'Missing url'}), 400
        
        print(f"\n🎬 STEALTH DOWNLOAD v2.6")
        print(f"🔗 URL: {url}")
        
        # Clean temp dir
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Try download with retries
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"🔄 Attempt {attempt + 1}/{max_attempts}")
            
            ydl_opts = get_stealth_ydl_opts()
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    print("⬇️ Starting stealth download...")
                    info = ydl.extract_info(url, download=True)
                    print(f"✅ Download complete: {info.get('title')}")
                
                # Find valid video
                video_file = find_valid_video(TEMP_DIR)
                if video_file:
                    file_size = os.path.getsize(video_file)
                    if file_size > MAX_FILE_SIZE:
                        os.remove(video_file)
                        return jsonify({'success': False, 'error': f'File too large: {file_size/(1024*1024):.1f}MB'}), 413
                    
                    # Safe filename
                    title = re.sub(r'[^\w\s-]', '_', info.get('title', 'video'))[:80]
                    safe_filename = f"{title}.mp4"
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
                
                else:
                    print(f"❌ Attempt {attempt + 1}: No valid video found")
                    if attempt < max_attempts - 1:
                        wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                        print(f"⏳ Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
                        return jsonify({
                            'success': False,
                            'error': f'No valid video after {max_attempts} attempts. Files: {files}'
                        }), 500
                
            except yt_dlp.DownloadError as e:
                print(f"❌ Download error (attempt {attempt + 1}): {str(e)}")
                if "429" in str(e) or "Too Many Requests" in str(e):
                    print("🔄 Rate limited - waiting longer...")
                    time.sleep(30 * (attempt + 1))
                elif attempt < max_attempts - 1:
                    time.sleep(10 * (attempt + 1))
                else:
                    return jsonify({'success': False, 'error': f'Download failed after {max_attempts} attempts: {str(e)}'}), 400
        
        return jsonify({'success': False, 'error': 'All download attempts failed'}), 500
        
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
    print(f"🎥 Starting Anti-Block Downloader v2.6")
    print(f"🌐 {host}:{port}")
    print("✅ Stealth mode + retries + MHTML rejection")
    app.run(host=host, port=port, debug=False, threaded=True)
