from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'Missing "url" parameter'}), 400
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return jsonify({
            'success': True,
            'title': info.get('title'),
            'author': info.get('uploader'),
            'length': info.get('duration'),
            'views': info.get('view_count'),
            'thumbnail': info.get('thumbnail')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    data = request.get_json()
    url = data.get('url')
    resolution = data.get('resolution', '360p')
    
    if not url:
        return jsonify({'success': False, 'error': 'Missing "url" parameter'}), 400
    
    temp_dir = tempfile.mkdtemp()
    try:
        ydl_opts = {
            'format': f'bestvideo[height<={resolution[:-1]}0][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            video_file = os.path.join(temp_dir, secure_filename(filename))
        
        if not os.path.exists(video_file):
            return jsonify({'success': False, 'error': 'Download failed'}), 500
        
        return send_file(
            video_file,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f"{info['title']}.mp4"
        )
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
