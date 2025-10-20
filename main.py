from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import shutil
import time

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
            'no_warnings': True,
            'extract_flat': False
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
    resolution = data.get('resolution', '360p')  # Force 360p max
    
    if not url:
        return jsonify({'success': False, 'error': 'Missing "url" parameter'}), 400
    
    temp_dir = tempfile.mkdtemp()
    
    # STREAM RESPONSE TO AVOID TIMEOUT
    def generate():
        try:
            # TIMEOUT-PROOF yt-dlp options
            ydl_opts = {
                # ⚡ FASTEST FORMAT: DASH MP4 (no HLS fragments)
                'format': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/worst[ext=mp4]',
                
                # ⚡ NO FRAGMENT DOWNLOADS
                'hls_use_mpegts': False,
                'hls_prefer_native_ts': False,
                'hls_use_mpegts_for_encrypted': False,
                
                # ⚡ TIMEOUT PROTECTION
                'socket_timeout': 30,
                'fragment_retries': 2,
                'retries': 2,
                
                # ⚡ FASTER DOWNLOAD
                'noplaylist': True,
                'no_warnings': True,
                'quiet': True,
                'extractaudio': False,
                
                # ⚡ OUTPUT
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                
                # ⚡ USER AGENT (helps YouTube)
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
            
            print(f"🚀 Starting download: {resolution} - {url}")
            start_time = time.time()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Find final MP4 file (handles .part files)
                video_file = None
                for ext in ['.mp4', '.mkv', '.webm']:
                    test_file = filename + ext
                    if os.path.exists(test_file):
                        video_file = test_file
                        break
                    # Check for .part files
                    part_file = test_file + '.part'
                    if os.path.exists(part_file):
                        os.rename(part_file, test_file)
                        video_file = test_file
                        break
                
                if not video_file or not os.path.exists(video_file):
                    yield f"ERROR: No video file found after download\n"
                    return
                
                file_size = os.path.getsize(video_file)
                print(f"✅ Downloaded: {video_file} ({file_size/1024/1024:.1f}MB in {time.time()-start_time:.1f}s)")
                
                # STREAM FILE
                with open(video_file, 'rb') as f:
                    while True:
                        chunk = f.read(8192)  # 8KB chunks
                        if not chunk:
                            break
                        yield chunk
                
        except Exception as e:
            print(f"❌ Download error: {str(e)}")
            yield f"ERROR: {str(e)}\n"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Return as streaming response
    return Response(
        generate(),
        mimetype='video/mp4',
        headers={
            'Content-Disposition': 'attachment; filename="video.mp4"',
            'Transfer-Encoding': 'chunked'
        }
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
