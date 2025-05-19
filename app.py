import os
import re
import sys
import subprocess
import shutil
import whisper
import nltk
import threading
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

# Status tracking for processing completion
processing_status = {"completed": False}

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

EXCEPTIONS = {"as", "pass", "bass"}

### Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)

### Serve Index Page ###
@app.route('/')
def serve_index():
    index_path = os.path.join(STATIC_FOLDER, "index.html")
    if os.path.exists(index_path):
        return send_file(index_path)
    return jsonify({"error": "index.html not found"}), 404

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

### Processing Function ###
def async_process_files():
    global processing_status
    try:
        processing_status["completed"] = False  # Reset status before processing
        mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
        mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

        convert_mp4_to_mp3(mp4_path, mp3_path)

        # Simulating processing (replace this with real logic)
        with open(os.path.join(PROCESSED_FOLDER, "timestamps.txt"), "w") as f:
            f.write("Sample Timestamp Data\n")

        with open(os.path.join(PROCESSED_FOLDER, "final.srt"), "w") as f:
            f.write("Sample SRT Data\n")

        processing_status["completed"] = True  # ✅ Update status after processing completes
    except Exception as e:
        processing_status["completed"] = False
        print(f"❌ Error in processing: {str(e)}")

### Process Route ###
@app.route('/process', methods=['GET'])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

### Status Route (Allows Front-end to Check Completion) ###
@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"status": "completed" if processing_status["completed"] else "in_progress"})

### Download Processed Files ###
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not found or empty"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
