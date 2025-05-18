import os
import re
import sys
import subprocess
import shutil
import whisper
import nltk
import threading
from nltk.stem import WordNetLemmatizer
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
STATIC_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB upload limit

# Install missing dependencies
REQUIRED_PACKAGES = ["nltk"]
def install_missing_packages():
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

install_missing_packages()
nltk.download('wordnet')
lemmatizer = WordNetLemmatizer()

EXCEPTIONS = {"as", "pass", "bass"}

### Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)

### Load Swear Words ###
def load_swears(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return {line.strip().lower() for line in file if line.strip().lower() not in EXCEPTIONS}

### Serve Index Page ###
@app.route('/')
def serve_index():
    return send_file(os.path.join(STATIC_FOLDER, "index.html"))

### File Upload Route ###
@app.route('/upload', methods=['POST'])
def upload_files():
    if 'ass_file' not in request.files or 'mp4_file' not in request.files:
        return jsonify({"error": "Missing ASS or MP4 file"}), 400

    ass_file = request.files['ass_file']
    mp4_file = request.files['mp4_file']

    ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")

    ass_file.save(ass_path)
    mp4_file.save(mp4_path)

    return jsonify({"success": True, "message": "Files uploaded successfully!"}), 200

### Background Processing to Prevent Timeout (Fix 3) ###
def async_process_files():
    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
    mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

    convert_mp4_to_mp3(mp4_path, mp3_path)
    censor_ass_file(ass_path, "swears.txt", "processed/output.ass", "processed/clean.txt", "processed/unclean.txt")

    audio_chunks = extract_audio_chunks(mp3_path, "processed/unclean.txt", "processed/audio_chunks")
    model = whisper.load_model("medium")
    transcribe_audio_chunks(audio_chunks, model)
    extract_matching_timestamps("processed/final.srt", "swears.txt", "processed/timestamps.txt")

    shutil.rmtree("processed/audio_chunks")
    os.remove(mp3_path)

### Process Route (Runs Asynchronously) (Fix 3) ###
@app.route('/process', methods=['GET'])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

### Download Processed Files ###
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not found or empty"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
