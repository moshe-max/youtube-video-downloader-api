#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.7 - LIGHTWEIGHT STEALTH
- No impersonate (avoids curl_cffi dependency)
- Simple user-agent rotation
- Aggressive retries + delays
- MHTML rejection
- Production ready for Render
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

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 LIGHTWEIGHT STEALTH CONFIG
# ================================

MAX_DURATION = 20 * 60
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

# Simple user agents (no impersonate needed)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# ================================
# 🛡️ BASIC STEALTH OPTIONS
# ================================

def get_stealth_ydl_opts():
    """Lightweight yt-dlp options - no impersonate"""
    return {
        # Basic stealth
        'user_agent': random.choice(USER_AGENTS),
        'referer': 'https://www.youtube.com/',
        
        # Aggressive retries for blocks
        'retries': 15,
        'fragment_retries': 15,
        'extractor_retries': 10,
        
        # Rate limiting delays
        'sleep_interval': 2,
        'max_sleep_interval': 10,
        'sleep_requests': 1,
        
        # Format: Best 720p video + audio → MP4
        'format': 'bestvideo[height<=720]+bestaudio[ext=m4a]/bestvideo[height<=720]/best[height<=720]/best',
        'merge_output_format': 'mp4',
        
        # NO JUNK FILES
        'writethumbnail': False,
        'write_all_thumbnails': False,
        'embed_thumbnail': False,
        'embed_metadata': False,
        'writesubtitles': False,
        'writeautomaticsub': False,
        'noplaylist': True,
        
        # Output
        'outtmpl': '%(title)s.%(ext)s',
        'paths': {'home': TEMP_DIR},
        
        # Verbose logging
        'quiet': False,
        'no_warnings': False,
    }

# ================================
# 🛠️ VIDEO VALIDATOR
# ================================

def is_valid_video_file(filepath):
    """Reject MHTML/HTML, validate video"""
    if not os.path.exists(filepath):
        return False
    
    filename = os.path.basename(filepath).lower()
    
    # Reject MHTML/HTML
    if filename.endswith(('.mhtml', '.html', '.htm')):
        print(f"❌ REJECT MHTML: {filename}")
        return False
    
    # Valid video extensions
    valid_exts = ['.mp4', '.mkv', '.webm', '.avi', '.mov']
    if not any(filename.endswith(ext) for ext in valid_exts):
        print(f"❌ INVALID EXT: {filename}")
        return False
    
    # Minimum size for video
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb < 1.0:
        print(f"❌ TOO SMALL: {filename} ({size_mb:.1f}MB)")
        return False
    
    print(f"✅ VALID VIDEO: {filename} ({size_mb:.1f}MB)")
    return True

def find_valid_video(temp_dir):
    """Find largest valid video file"""
    if not os.path.exists(temp_dir):
        return None
    
    all_files = os.listdir(temp_dir)
    video_files = []
    
    for filename in all_files:
        filepath = os.path.join(temp_dir, filename)
        if os.path.isfile(filepath) and is_valid_video_file(filepath):
            video_files.append(filepath)
    
    if not video_files:
        # Debug: show all files
        debug_files = {}
        for f in all_files:
            path = os.path.join(temp_dir, f)
            if os.path.isfile(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                debug_files[f] = f"{size_mb:.1f}MB"
        print(f"❌ NO VALID VIDEOS! Files: {debug_files}")
        return None
    
    # Return largest valid video
    largest = max(video_files, key=os.path.getsize)
    size_mb = os.path.getsize(largest) / (1024 * 1024)
    print(f"✅ SELECTED: {os.path.basename(largest)} ({size_mb:.1f}MB)")
    return largest

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.7',
        'message': '🎥 Lightweight Stealth Downloader',
        'temp_dir': TEMP_DIR,
        'temp_dir_exists': os.path.exists(TEMP_DIR)
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
        ydl_opts = get_stealth_ydl_opts()
        ydl_opts.update({
            'quiet': True,
            'no_warnings': True,
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
                result['error'] = f'Video too long ({result["length"]}s)'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Info failed: {str(e)}'}), 500

# ================================
# ⬇️ LIGHTWEIGHT DOWNLOAD
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
        
        print(f"\n🎬 LIGHTWEIGHT DOWNLOAD v2.7")
        print(f"🔗 URL: {url}")
        
        # Clean temp dir
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Download with multiple attempts
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"\n🔄 ATTEMPT {attempt + 1}/{max_attempts}")
            print(f"🕐 User-Agent: {random.choice(USER_AGENTS)}")
            
            ydl_opts = get_stealth_ydl_opts()
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    print("⬇️ Starting download...")
                    info = ydl.extract_info(url, download=True)
                    print(f"✅ DOWNLOAD COMPLETE: {info.get('title')}")
                
                # Find valid video file
                video_file = find_valid_video(TEMP_DIR)
                if video_file:
                    file_size = os.path.getsize(video_file)
                    
                    if file_size > MAX_FILE_SIZE:
                        os.remove(video_file)
                        return jsonify({
                            'success': False,
                            'error': f'File too large: {file_size/(1024*1024):.1f}MB'
                        }), 413
                    
                    # Create safe filename
                    title = re.sub(r'[^\w\s-]', '_', info.get('title', 'video'))[:80]
                    safe_filename = f"{title}.mp4"
                    
                    print(f"📤 SENDING: {safe_filename} ({file_size/(1024*1024):.1f}MB)")
                    
                    response = send_file(
                        video_file,
                        mimetype='video/mp4',
                        as_attachment=True,
                        download_name=safe_filename,
                        conditional=True,
                        max_age=0  # No caching
                    )
                    
                    # Auto-cleanup
                    @response.call_on_close
                    def cleanup():
                        try:
                            if os.path.exists(video_file):
                                os.remove(video_file)
                            shutil.rmtree(TEMP_DIR, ignore_errors=True)
                            print("🧹 CLEANUP COMPLETE")
                        except Exception as e:
                            print(f"⚠️ CLEANUP ERROR: {e}")
                    
                    return response
                
                else:
                    print(f"❌ ATTEMPT {attempt + 1}: No valid video found")
                    
            except yt_dlp.DownloadError as e:
                error_msg = str(e)
                print(f"❌ DOWNLOAD ERROR: {error_msg}")
                
                # Handle specific errors
                if any(x in error_msg.lower() for x in ['429', 'too many requests', 'rate limit']):
                    print("🔄 RATE LIMITED - LONG WAIT...")
                    wait_time = 60 * (attempt + 1)  # 1min, 2min, 3min
                elif any(x in error_msg.lower() for x in ['signature', 'precondition']):
                    print("🔄 ANTI-BOT BLOCK - RETRYING...")
                    wait_time = 30 * (attempt + 1)
                else:
                    wait_time = 10 * (attempt + 1)
                
                if attempt < max_attempts - 1:
                    print(f"⏳ WAITING {wait_time}s BEFORE RETRY...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
                    return jsonify({
                        'success': False,
                        'error': f'All {max_attempts} attempts failed. Last error: {error_msg}. Files: {files}'
                    }), 500
            
            except Exception as e:
                print(f"❌ UNEXPECTED ERROR: {str(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(10 * (attempt + 1))
                else:
                    return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500
        
        return jsonify({'success': False, 'error': 'Download failed after all retries'}), 500
        
    except Exception as e:
        print(f"❌ SERVER ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

# ================================
# 🚀 SERVER START
# ================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"🎥 Starting Lightweight Stealth API v2.7")
    print(f"🌐 Host: {host}:{port}")
    print(f"📁 Temp: {TEMP_DIR}")
    print("✅ No impersonate - Simple UA rotation + retries")
    print("✅ Rejects MHTML - Validates MP4 only")
    
    app.run(host=host, port=port, debug=False, threaded=True)
