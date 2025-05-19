import os
import re
import sys
import subprocess
import shutil
import whisper
import nltk
import threading
import json
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

### Extract Short Audio Segments for Faster Whisper Processing ###
def extract_audio_segments(mp3_path, subtitle_file):
    timestamp_audio_folder = os.path.join(PROCESSED_FOLDER, "timestamp_audio")
    os.makedirs(timestamp_audio_folder, exist_ok=True)

    timestamps = []
    with open(subtitle_file, "r", encoding="utf-8") as f:
        subtitle_lines = f.readlines()
    
    for i, line in enumerate(subtitle_lines):
        if "-->" in line:
            start_time, end_time = line.split("-->")
            start_time = start_time.strip()
            end_time = end_time.strip()

            timestamps.append((start_time, end_time))

            output_segment = os.path.join(timestamp_audio_folder, f"segment_{i}.mp3")
            subprocess.run(["ffmpeg", "-y", "-i", mp3_path, "-ss", start_time, "-to", end_time, "-q:a", "0", "-map", "a", output_segment], check=True)
    
    return timestamps, timestamp_audio_folder

### Generate Timestamps & Final SRT ###
def process_audio_for_timestamps(mp3_path):
    subtitle_file = os.path.join(PROCESSED_FOLDER, "output.ass")
    timestamps_file = os.path.join(PROCESSED_FOLDER, "timestamps.txt")
    final_srt_file = os.path.join(PROCESSED_FOLDER, "final.srt")

    timestamps, audio_segments_folder = extract_audio_segments(mp3_path, subtitle_file)

    whisper_model = whisper.load_model("small")  # ✅ Efficient model for lower CPU usage

    srt_lines = []
    timestamps_output = []

    for i, (start_time, end_time) in enumerate(timestamps):
        segment_audio = os.path.join(audio_segments_folder, f"segment_{i}.mp3")
        if os.path.exists(segment_audio):
            result = whisper_model.transcribe(segment_audio)
            text = result["text"].strip()

            srt_lines.append(f"{i+1}\n{start_time} --> {end_time}\n{text}\n")
            timestamps_output.append(f"{start_time} {text}")

    with open(final_srt_file, "w", encoding="utf-8") as f:
        f.writelines(srt_lines)

    with open(timestamps_file, "w", encoding="utf-8") as f:
        f.writelines("\n".join(timestamps_output))

    shutil.rmtree(audio_segments_folder)  # ✅ Cleanup temporary audio files

### Background Processing ###
def async_process_files():
    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
    mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

    convert_mp4_to_mp3(mp4_path, mp3_path)

    censor_ass_file(ass_path, "swears.txt", "processed/output.ass", "processed/clean.txt", "processed/unclean.txt")

    process_audio_for_timestamps(mp3_path)  # ✅ Efficient timestamp and SRT generation

    os.remove(mp3_path)  # ✅ Cleanup MP3 after processing

### Process Route ###
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
