import os
import time
from flask import Flask, request, jsonify
import yt_dlp

app = Flask(__name__)

# Validate API key
def validate_api_key(request):
    api_key = os.getenv('API_KEY')
    if not api_key:
        return False, "API key not configured"
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != f"Bearer {api_key}":
        return False, "Invalid or missing API key"
    return True, None

# YouTube download function with retry logic for 429 errors
def download_video(url, output_dir='/tmp'):
    retries = int(os.getenv('DOWNLOAD_RETRIES', 3))
    delay = int(os.getenv('RETRY_DELAY', 1))

    for attempt in range(retries):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'merge_output_format': 'mp4'
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            return True, filename
        except Exception as e:
            if '429' in str(e):
                time.sleep(delay * (2 ** attempt))  # Exponential backoff
            else:
                return False, str(e)
    return False, 'Max retries exceeded'

# API endpoint for downloading YouTube videos
@app.route('/download', methods=['POST'])
def download_youtube():
    # Validate API key
    is_valid, error = validate_api_key(request)
    if not is_valid:
        return jsonify({'error': error}), 401

    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    success, result = download_video(url)
    if success:
        return jsonify({'status': 'success', 'file': result}), 200
    else:
        return jsonify({'status': 'error', 'message': result}), 500

# Health check endpoint for Render
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
