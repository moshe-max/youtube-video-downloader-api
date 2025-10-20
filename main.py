from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pytube import YouTube
import io
import os

app = Flask(__name__)
CORS(app)  # Fix CORS for browser testing

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': '🎥 YouTube Downloader API LIVE!',
        'version': '2.0',
        'endpoints': {
            'GET /health': 'Health check',
            'GET /info?url=<youtube_url>': 'Get video info',
            'POST /download': 'Download video',
            'GET /': 'This page'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': os.environ.get('RENDER_SERVICE_NAME', 'local')})

@app.route('/info', methods=['GET'])
def get_video_info():
    """GET /info?url=https://youtube.com/watch?v=VIDEO_ID"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Missing "url" parameter'}), 400
    
    try:
        yt = YouTube(url)
        return jsonify({
            'success': True,
            'title': yt.title,
            'author': yt.author,
            'length': yt.length,
            'views': yt.views,
            'thumbnail': yt.thumbnail_url,
            'url': url,
            'duration_formatted': f"{yt.length//60}:{yt.length%60:02d}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download_video():
    """POST /download with JSON: {"url": "...", "resolution": "720p"}"""
    try:
        data = request.get_json()
        url = data.get('url')
        resolution = data.get('resolution', '720p')
        
        if not url:
            return jsonify({'error': 'Missing "url" in JSON'}), 400
        
        yt = YouTube(url)
        stream = yt.streams.filter(res=resolution, file_extension='mp4').first()
        
        if not stream:
            available = [s.res for s in yt.streams.filter(file_extension='mp4')]
            return jsonify({
                'error': f'No {resolution} available',
                'available': list(set(available))
            }), 400
        
        # Stream to browser/memory
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
                'Content-Length': str(stream.filesize)
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
