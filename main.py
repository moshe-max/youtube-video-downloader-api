from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pytube import YouTube
from urllib.parse import urlparse, parse_qs
import re
import io
import os

app = Flask(__name__)
CORS(app)

def is_valid_youtube_url(url):
    """Flexible YouTube URL validation"""
    if not url:
        return False
    
    # Extract video ID from various formats
    patterns = [
        r'(?:youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return True
    return False

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🎥 YouTube Downloader API v2.0 - FIXED!',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /info?url=<youtube_url>': 'Get video info',
            'POST /download': 'Download video {"url": "...", "resolution": "720p"}'
        },
        'status': '🟢 LIVE'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'api_version': '2.0-fixed'})

@app.route('/info', methods=['GET'])
def get_video_info():
    """FIXED: GET /info?url=https://youtube.com/watch?v=VIDEO_ID"""
    
    # Get and clean URL
    url = request.args.get('url', '').strip()
    print(f"🔍 DEBUG: Raw URL received: '{url}'")
    
    if not url:
        return jsonify({'success': False, 'error': 'Missing "url" parameter'}), 400
    
    # Basic validation
    if not ('youtube.com' in url or 'youtu.be' in url):
        return jsonify({
            'success': False, 
            'error': 'URL must contain youtube.com or youtu.be',
            'received_url': url
        }), 400
    
    # Extract video ID for validation
    video_id = None
    patterns = [
        r'(?:v=)([a-zA-Z0-9_-]{11})',
        r'(?:youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'(?:\/v\/)([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break
    
    if not video_id or len(video_id) != 11:
        return jsonify({
            'success': False,
            'error': 'Invalid YouTube video ID',
            'url': url,
            'extracted_id': video_id
        }), 400
    
    print(f"✅ Valid video ID: {video_id}")
    
    try:
        print(f"📺 Initializing YouTube: {url}")
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
        
        print(f"✅ SUCCESS: {yt.title}")
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'title': yt.title or 'Unknown Title',
            'author': yt.author or 'Unknown Author',
            'length': yt.length or 0,
            'views': yt.views or 0,
            'thumbnail': yt.thumbnail_url or '',
            'url': url,
            'duration': f"{yt.length//60}:{yt.length%60:02d}" if yt.length else '0:00',
            'publish_date': str(yt.publish_date) if yt.publish_date else 'Unknown'
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Pytube Error: {error_msg}")
        return jsonify({
            'success': False,
            'error': f'Failed to fetch video: {error_msg}',
            'video_id': video_id,
            'url': url
        }), 400

@app.route('/download', methods=['POST'])
def download_video():
    """POST /download - {"url": "...", "resolution": "720p"}"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data'}), 400
            
        url = data.get('url', '').strip()
        resolution = data.get('resolution', '720p')
        
        if not url:
            return jsonify({'success': False, 'error': 'Missing "url" in JSON'}), 400
        
        # Same validation as /info
        if not is_valid_youtube_url(url):
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
        
        print(f"⬇️ Downloading {resolution}: {url}")
        yt = YouTube(url)
        
        # Find best matching stream
        streams = yt.streams.filter(file_extension='mp4', progressive=True)
        stream = streams.get_by_resolution(resolution) or streams.first()
        
        if not stream:
            available = [s.res for s in streams if s.res]
            return jsonify({
                'success': False,
                'error': f'No {resolution} stream available',
                'available_resolutions': list(set(available))
            }), 400
        
        print(f"✅ Stream found: {stream.res} ({stream.filesize / (1024*1024):.1f}MB)")
        
        def generate():
            buffer = io.BytesIO()
            stream.stream_to_buffer(buffer)
            buffer.seek(0)
            return buffer.getvalue()
        
        return Response(
            generate(),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{yt.title[:50]}_{resolution}.mp4"',
                'Content-Length': str(stream.filesize),
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
        
    except Exception as e:
        print(f"❌ Download Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
