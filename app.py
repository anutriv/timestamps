import os
import re
import sys
import subprocess
import shutil
import nltk
import threading
import json
import wave
import requests
from vosk import Model, KaldiRecognizer
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
PROCESSED_FOLDER = os.path.join(os.getcwd(), "processed")
STATIC_FOLDER = os.path.join(os.getcwd(), "static")
VOSK_MODEL_PATH = os.path.join(os.getcwd(), "vosk-model")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB upload limit

processing_status = {"completed": False}

REQUIRED_PACKAGES = ["nltk"]
def install_missing_packages():
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

install_missing_packages()
nltk.download("wordnet")

EXCEPTIONS = {"as", "pass", "bass"}
lemmatizer = nltk.stem.WordNetLemmatizer()

SWEAR_WORDS = ["damn", "hell", "shit", "fuck", "bitch", "bastard"]

### **🔹 Automatic Vosk Model Download at Startup**
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip"

if not os.path.exists(VOSK_MODEL_PATH):
    print("🔹 Downloading Vosk model for the first time...")
    r = requests.get(VOSK_MODEL_URL, stream=True)
    with open("vosk-model.zip", "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)

    print("✅ Extracting Vosk model...")
    subprocess.run(["unzip", "vosk-model.zip", "-d", VOSK_MODEL_PATH])
    print("✅ Vosk model downloaded!")

### **Serve index.html at `/`**
@app.route("/")
def serve_index():
    return send_file(os.path.join(STATIC_FOLDER, "index.html"))

### **✅ Fix for JSON Response in Upload Endpoint**
@app.route("/upload", methods=["POST"])
def upload_files():
    try:
        if 'ass_file' not in request.files or 'mp4_file' not in request.files:
            return jsonify({"error": "Missing ASS or MP4 file"}), 400

        ass_file = request.files["ass_file"]
        mp4_file = request.files["mp4_file"]

        ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
        mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")

        ass_file.save(ass_path)
        mp4_file.save(mp4_path)

        return jsonify({"success": True, "message": "Files uploaded. Click 'Start Processing' to begin."}), 200

    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500  

### Step 1: Convert MP4 to MP3 First ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    print(f"🔹 Converting {input_mp4} to MP3...")
    subprocess.run(["ffmpeg", "-y", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)
    print(f"✅ MP3 saved at {output_mp3}")

### Step 2: Extract Clean, Unclean & Output.ass ###
def process_subtitles(ass_path):
    clean_file = os.path.join(PROCESSED_FOLDER, "clean.txt")
    unclean_file = os.path.join(PROCESSED_FOLDER, "unclean.txt")

    with open(ass_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    clean_lines = []
    unclean_lines = []

    for line in lines:
        text = line.strip()
        if re.search(r"[a-zA-Z]", text):
            clean_lines.append(text)
        else:
            unclean_lines.append(text)

    with open(clean_file, "w", encoding="utf-8") as f:
        f.write("\n".join(clean_lines))

    with open(unclean_file, "w", encoding="utf-8") as f:
        f.write("\n".join(unclean_lines))

### Step 3: Extract Audio Chunks Based on Clean.txt ###
def extract_required_chunks(mp3_path, clean_file, segment_folder):
    os.makedirs(segment_folder, exist_ok=True)

    with open(clean_file, "r", encoding="utf-8") as f:
        clean_lines = f.readlines()

    segment_time = 5
    total_lines = len(clean_lines)  # ✅ Only process exact number of lines

    for idx in range(total_lines):
        output_segment = os.path.join(segment_folder, f"segment_{idx:03d}.wav")

        print(f"🔹 Extracting chunk {idx} for subtitle {idx+1}/{total_lines}...")
        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path, "-ss", str(idx * segment_time), "-t", str(segment_time), 
            "-ac", "1", "-ar", "16000", "-vn", "-f", "wav", output_segment
        ], check=True)

        if not os.path.exists(output_segment) or os.path.getsize(output_segment) == 0:
            print(f"❌ Failed to create {output_segment} - Skipping.")

### ✅ Updated `async_process_files()` ###
def async_process_files():
    global processing_status
    processing_status["completed"] = False

    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")
    clean_file = os.path.join(PROCESSED_FOLDER, "clean.txt")
    segment_folder = os.path.join(PROCESSED_FOLDER, "audio_segments")

    convert_mp4_to_mp3(mp4_path, mp3_path)
    os.remove(mp4_path)

    process_subtitles(os.path.join(UPLOAD_FOLDER, "input.ass"))

    extract_required_chunks(mp3_path, clean_file, segment_folder)
    os.remove(mp3_path)

    processing_status["completed"] = True

@app.route("/process", methods=["GET"])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
