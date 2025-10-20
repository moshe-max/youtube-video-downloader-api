from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import re
import io
import os

app = Flask(__name__)
CORS(app)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🎥 YouTube Downloader API v3.0 - yt-dlp POWERED!',
        'status': '🟢 LIVE & RELIABLE',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /info?url=<youtube_url>': 'Video info',
            'POST /download': 'Download {"url": "...", "resolution": "720p"}'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'downloader': 'yt-dlp'})

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url', '').strip()
    print(f"🔍 Processing URL: {url}")
    
    if not url:
        return jsonify({'success': False, 'error': 'Missing url parameter'}), 400
    
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
    
    print(f"✅ Video ID: {video_id}")
    
    # yt-dlp configuration for metadata only
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Don't download, just get info
        'ignoreerrors': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info or 'entries' in info:
                return jsonify({'success': False, 'error': 'Video not found or private'}), 404
            
            print(f"✅ Video loaded: {info.get('title', 'Unknown')}")
            
            duration = int(info.get('duration', 0))
            views = int(info.get('view_count', 0))
            
            return jsonify({
                'success': True,
                'video_id': video_id,
                'title': info.get('title', 'Unknown'),
                'author': info.get('uploader', 'Unknown'),
                'length': duration,
                'views': views,
                'thumbnail': info.get('thumbnail', ''),
                'url': url,
                'duration': f"{duration//60}:{duration%60:02d}",
                'formats': [f.res for f in info.get('formats', []) if f.get('vcodec') != 'none']
            })
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ yt-dlp failed: {error_msg}")
        return jsonify({
            'success': False,
            'error': f'Failed to fetch video: {error_msg}',
            'video_id': video_id
        }), 400

@app.route('/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        resolution = data.get('resolution', '720p').lower()
        
        if not url:
            return jsonify({'success': False, 'error': 'Missing url in JSON'}), 400
        
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
        
        print(f"⬇️ Downloading {resolution}p: {video_id}")
        
        # yt-dlp options for video download
        ydl_opts = {
            'format': f'best[height<={resolution[:-1]}][ext=mp4]/best[ext=mp4]/best',
            'outtmpl': f'%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get info first
            info = ydl.extract_info(url, download=True)
            
            # Find downloaded file
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                return jsonify({'success': False, 'error': 'Download failed - file not found'}), 500
            
            # Read file and stream
            with open(filename, 'rb') as f:
                file_data = f.read()
            
            # Clean up
            os.remove(filename)
            
            print(f"✅ Downloaded: {len(file_data)/1024/1024:.1f}MB")
            
            return Response(
                file_data,
                mimetype='video/mp4',
                headers={
                    'Content-Disposition': f'attachment; filename="{info.get("title", "video")}_{resolution}.mp4"',
                    'Content-Length': str(len(file_data))
                }
            )
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Download failed: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)