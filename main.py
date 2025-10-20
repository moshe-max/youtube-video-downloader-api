from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pytube import YouTube
import re
import io
import os
import time

app = Flask(__name__)
CORS(app)

def extract_video_id(url):
    """Extract 11-char video ID from any YouTube URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:\/v\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🎥 YouTube Downloader API v2.1 - Pytube 12.1.3 Fixed!',
        'status': '🟢 LIVE',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /info?url=<youtube_url>': 'Video info',
            'POST /download': 'Download video'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'version': '2.1'})

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url', '').strip()
    
    print(f"🔍 Processing URL: {url}")
    
    if not url:
        return jsonify({'success': False, 'error': 'Missing url parameter'}), 400
    
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
    
    print(f"✅ Video ID extracted: {video_id}")
    
    try:
        # Pytube 12.1.3 needs these settings
        yt = YouTube(
            url,
            use_oauth=False,
            allow_oauth_cache=True,
            proxies=None
        )
        
        print(f"✅ Video loaded: {yt.title}")
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'title': yt.title or 'Unknown',
            'author': yt.author or 'Unknown',
            'length': int(yt.length) if yt.length else 0,
            'views': int(yt.views) if yt.views else 0,
            'thumbnail': yt.thumbnail_url or '',
            'url': url,
            'duration': f"{int(yt.length)//60}:{int(yt.length)%60:02d}" if yt.length else '0:00'
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Pytube failed: {error_msg}")
        return jsonify({
            'success': False,
            'error': f'Pytube error: {error_msg}',
            'video_id': video_id,
            'url': url
        }), 400

@app.route('/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        resolution = data.get('resolution', '720p')
        
        if not url:
            return jsonify({'success': False, 'error': 'Missing url in JSON'}), 400
        
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'success': False, 'error': 'Invalid YouTube URL'}), 400
        
        print(f"⬇️ Downloading {resolution}p: {video_id}")
        
        yt = YouTube(url)
        
        # Filter for progressive MP4 streams (smaller files)
        streams = yt.streams.filter(
            file_extension='mp4',
            progressive=True
        ).order_by('resolution').desc()
        
        stream = None
        for s in streams:
            if resolution.lower() in s.resolution.lower():
                stream = s
                break
        
        if not stream:
            # Fallback to highest quality
            stream = streams.first()
        
        if not stream:
            return jsonify({
                'success': False,
                'error': 'No suitable video stream found',
                'available': [s.res for s in streams]
            }), 400
        
        print(f"✅ Stream: {stream.res} ({stream.filesize/1024/1024:.1f}MB)")
        
        def generate():
            buffer = io.BytesIO()
            try:
                stream.stream_to_buffer(buffer)
                buffer.seek(0)
                return buffer.getvalue()
            except Exception as e:
                print(f"❌ Stream error: {e}")
                raise e
        
        return Response(
            generate(),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{yt.title[:50]}_{stream.res}.mp4"',
                'Content-Length': str(stream.filesize)
            }
        )
        
    except Exception as e:
        print(f"❌ Download failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)