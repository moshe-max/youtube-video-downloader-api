#!/usr/bin/env python3
"""
🎥 YT DOWNLOADER API v2.5 - DASH + AUTO-MERGE
- Handles modern YouTube DASH streams
- Auto-merges video + audio → MP4
- Robust format selection
- Production ready
"""

import os
import re
import json
import shutil
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import glob

app = Flask(__name__)
CORS(app)

# ================================
# 🔧 CONFIGURATION
# ================================

MAX_DURATION = 20 * 60
ALLOWED_RESOLUTIONS = ['360p', '480p', '720p']
DEFAULT_RESOLUTION = '720p'
MAX_FILE_SIZE = 50 * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp()

# ================================
# 🛠️ UNIVERSAL FORMAT SELECTOR
# ================================

def get_best_format(url, target_resolution):
    """Get best format - handles DASH + progressive MP4"""
    print(f"🔍 Analyzing formats for {target_resolution}...")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # Count available formats
        video_formats = []
        audio_formats = []
        
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('height'):  # Video streams
                video_formats.append({
                    'format_id': f.get('format_id'),
                    'height': f.get('height'),
                    'ext': f.get('ext'),
                    'filesize': f.get('filesize', 0)
                })
            elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':  # Audio only
                audio_formats.append(f.get('format_id'))
        
        print(f"📊 Video formats: {len(video_formats)}")
        print(f"📊 Audio formats: {len(audio_formats)}")
        
        # Show top video formats
        sorted_videos = sorted(video_formats, key=lambda x: x['height'], reverse=True)[:5]
        for fmt in sorted_videos:
            size = fmt['filesize'] / (1024*1024) if fmt['filesize'] else '?'
            print(f"  {fmt['format_id']}: {fmt['height']}p {fmt['ext']} ({size:.1f}MB)")
        
        target_height = int(target_resolution[:-1])
        
        # Strategy 1: Progressive MP4 (video + audio combined)
        progressive_mp4 = None
        for fmt in video_formats:
            if (fmt['ext'] == 'mp4' and 
                fmt['height'] <= target_height and 
                fmt.get('acodec') != 'none'):
                progressive_mp4 = fmt['format_id']
                print(f"✅ Progressive MP4 found: {progressive_mp4} ({fmt['height']}p)")
                return f"{progressive_mp4}", {'type': 'progressive', 'height': fmt['height']}
        
        # Strategy 2: DASH merge (best video + best audio)
        best_video = None
        best_height = 0
        
        for fmt in video_formats:
            height = fmt['height']
            if height <= target_height and height > best_height:
                best_video = fmt['format_id']
                best_height = height
        
        if best_video:
            # Merge with best audio
            format_selector = f"{best_video}+bestaudio[ext=m4a]/best[height<={target_height}]"
            print(f"✅ DASH merge: {best_video} ({best_height}p) + audio")
            return format_selector, {'type': 'dash', 'height': best_height, 'video_id': best_video}
        
        # Strategy 3: Best available
        if video_formats:
            best_fmt = max(video_formats, key=lambda x: x['height'])
            format_selector = f"{best_fmt['format_id']}+bestaudio/best"
            print(f"⚠️ Fallback: {best_fmt['format_id']} ({best_fmt['height']}p)")
            return format_selector, {'type': 'fallback', 'height': best_fmt['height']}
        
        return 'best', {'type': 'best', 'height': 'unknown'}

# ================================
# 🛠️ FILE FINDER
# ================================

def find_video_file(temp_dir):
    """Find final merged video file"""
    if not os.path.exists(temp_dir):
        return None
    
    all_files = os.listdir(temp_dir)
    video_exts = ['.mp4', '.mkv', '.webm']
    video_files = [f for f in all_files if any(f.endswith(ext) for ext in video_exts)]
    
    print(f"📁 Final files: {video_files}")
    
    if video_files:
        # Pick largest (usually merged file)
        largest = max(video_files, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
        filepath = os.path.join(temp_dir, largest)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"✅ Selected: {largest} ({size_mb:.1f}MB)")
        return filepath
    
    # Debug: show all files
    debug = {}
    for f in all_files:
        path = os.path.join(temp_dir, f)
        if os.path.isfile(path):
            size = os.path.getsize(path) / (1024 * 1024)
            debug[f] = f"{size:.1f}MB"
    print(f"❌ No final video! Raw files: {debug}")
    return None

# ================================
# 🏥 HEALTH CHECK
# ================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '2.5',
        'message': '🎥 DASH + Merge YouTube Downloader'
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
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Count video formats
            video_count = sum(1 for f in info.get('formats', []) if f.get('vcodec') != 'none')
            
            result = {
                'success': True,
                'id': info.get('id'),
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'length': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'video_formats': video_count,
                'can_download': True
            }
            
            if result['length'] > MAX_DURATION:
                result['can_download'] = False
                result['error'] = f'Video too long ({result["length"]}s)'
            
            return jsonify(result)
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Info failed: {str(e)}'}), 500

# ================================
# ⬇️ UNIVERSAL DOWNLOAD
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
        
        print(f"\n🎬 DOWNLOAD START v2.5")
        print(f"🔗 URL: {url}")
        print(f"📐 Target: {resolution}")
        
        # Clean temp dir
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Get best format
        format_selector, format_info = get_best_format(url, resolution)
        print(f"📐 Format: {format_selector}")
        print(f"📊 Strategy: {format_info}")
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': '%(title)s.%(ext)s',
            'merge_output_format': 'mp4',  # Always merge to MP4
            
            # Debug
            'quiet': False,
            'no_warnings': False,
            
            # NO EXTRAS
            'writethumbnail': False,
            'write_all_thumbnails': False,
            'embed_thumbnail': False,
            'noplaylist': True,
            
            # Paths
            'paths': {'home': TEMP_DIR},
        }
        
        print("⬇️ Downloading...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            print(f"✅ Complete: {info.get('title')}")
        
        # Find final MP4
        video_file = find_video_file(TEMP_DIR)
        if not video_file:
            files = os.listdir(TEMP_DIR) if os.path.exists(TEMP_DIR) else []
            return jsonify({
                'success': False,
                'error': f'No video file. Files: {files}'
            }), 500
        
        file_size = os.path.getsize(video_file)
        if file_size > MAX_FILE_SIZE:
            os.remove(video_file)
            return jsonify({'success': False, 'error': f'File too large: {file_size/(1024*1024):.1f}MB'}), 413
        
        # Safe filename
        title = re.sub(r'[^\w\s-]', '_', info.get('title', 'video'))[:80]
        safe_filename = f"{title}_{format_info['height']}p.mp4"
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
                print("🧹 Cleanup done")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")
        
        return response
        
    except yt_dlp.DownloadError as e:
        print(f"❌ Download error: {str(e)}")
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
    print(f"🎥 Starting Universal Downloader v2.5")
    print(f"🌐 {host}:{port}")
    print("✅ Handles DASH + progressive MP4")
    app.run(host=host, port=port, debug=False, threaded=True)
