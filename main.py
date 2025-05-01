from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
import yt_dlp
import os
import uuid
import zipfile
import json
import re
from io import BytesIO
from yt_dlp import YoutubeDL

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['DOWNLOAD_FOLDER'] = 'downloads'

# Create downloads directory if it doesn't exist
try:
    os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create downloads directory: {e}")

@app.route('/search', methods=['POST'])
def search():
    try:
        query = request.form['query']
        if not query:
            return jsonify({"error": "Please enter a search query"}), 400

        # Use yt-dlp to search for videos
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f'ytsearch5:{query}', download=False)

        videos = []
        if 'entries' in search_results:
            for video in search_results['entries']:
                videos.append({
                    'id': video.get('id'),
                    'title': video.get('title'),
                    'url': f'https://www.youtube.com/watch?v={video.get("id")}',
                    'thumbnail': video.get('thumbnail'),
                    'duration': video.get('duration'),
                    'uploader': video.get('uploader')
                })

        return jsonify({"videos": videos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download-all', methods=['GET'])
def download_all():
    try:
        # Get all files in the downloads directory
        download_dir = app.config['DOWNLOAD_FOLDER']
        files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) 
                if os.path.isfile(os.path.join(download_dir, f))]
        
        if not files:
            flash('No files found in downloads directory.')
            return redirect(url_for('home'))
        
        # Create a zip file with all files
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                zipf.write(file, os.path.basename(file))
                print(f"Added {file} to zip archive")
        
        memory_file.seek(0)
        return send_file(memory_file, download_name='all_downloads.zip', 
                        as_attachment=True, mimetype='application/zip')
    
    except Exception as e:
        flash(f'Error: {str(e)}')
        return redirect(url_for('home'))

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Get URLs (split by new lines)
            urls_text = request.form['urls']
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]

            if not urls:
                flash('Please enter at least one YouTube URL')
                return redirect(url_for('home'))

            downloaded_files = []

            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(app.config['DOWNLOAD_FOLDER'], '%(title)s.%(ext)s'),
                'continue': True,  # Resume partial downloads
                'retries': 10,     # Retry on errors
                'fragment_retries': 10,
                'ignoreerrors': True,
                'quiet': True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for url in urls:
                    try:
                        ydl.download([url])
                        info_dict = ydl.extract_info(url, download=False)
                        filename = os.path.join(app.config['DOWNLOAD_FOLDER'], ydl.prepare_filename(info_dict))
                        if os.path.exists(filename):
                            downloaded_files.append(filename)
                            print(f"Downloaded: {filename}")
                    except Exception as e:
                        flash(f'Error downloading {url}: {str(e)}')
                        print(f"Error downloading {url}: {str(e)}")

            # If no files were downloaded successfully
            if not downloaded_files:
                flash('No files were downloaded successfully. Please check your URLs.')
                return redirect(url_for('home'))

            # If only one file, send it directly
            if len(downloaded_files) == 1:
                return send_file(downloaded_files[0], as_attachment=True)

            # If multiple files, create a zip file
            memory_file = BytesIO()
            with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in downloaded_files:
                    # Ensure file exists before adding to zip
                    if os.path.exists(file):
                        zipf.write(file, os.path.basename(file))
                        print(f"Added {file} to zip archive")
                    else:
                        print(f"Warning: File {file} does not exist and was not added to the zip")

            # Check if the zip has any files
            memory_file.seek(0)
            if len(downloaded_files) > 0:
                print(f"Sending zip with {len(downloaded_files)} files")
                return send_file(memory_file, download_name='youtube_downloads.zip', as_attachment=True, mimetype='application/zip')
            else:
                flash('No files were downloaded successfully.')
                return redirect(url_for('home'))

        except Exception as e:
            flash(f'Error: {str(e)}')
            return redirect(url_for('home'))

    return render_template('index.html')

if __name__ == '__main__':
    print("Starting YouTube MP3 Downloader server...")
    app.run(host='0.0.0.0', port=8080, debug=True)