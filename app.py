import os
import re
import sys
import subprocess
import shutil
import nltk
import threading
import time
import whisper
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
PROCESSED_FOLDER = os.path.join(os.getcwd(), "processed")
STATIC_FOLDER = os.path.join(os.getcwd(), "static")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB upload limit

processing_status = {"completed": False}

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
lemmatizer = nltk.stem.WordNetLemmatizer()

### **Whisper Model Persistence: Prevent Redundant Downloads**
WHISPER_CACHE_DIR = os.path.join(os.getcwd(), "whisper_models")
os.makedirs(WHISPER_CACHE_DIR, exist_ok=True)  # ✅ Ensure persistent directory exists

def load_whisper_once():
    MODEL_PATH = os.path.join(WHISPER_CACHE_DIR, "tiny.pt")

    if not os.path.exists(MODEL_PATH):
        print("🔹 Downloading Whisper model for the first time...")
        global whisper_model
        whisper_model = whisper.load_model("tiny", download_root=WHISPER_CACHE_DIR)
        print("✅ Whisper model downloaded and cached.")
    else:
        print("✅ Using cached Whisper model!")
        global whisper_model
        whisper_model = whisper.load_model("tiny", download_root=WHISPER_CACHE_DIR)

# ✅ Call this function manually **before starting the Flask app**
load_whisper_once()

### Step 1: Extract Clean, Unclean & Output.ass ###
def process_subtitles(ass_path):
    clean_file = os.path.join(PROCESSED_FOLDER, "clean.txt")
    unclean_file = os.path.join(PROCESSED_FOLDER, "unclean.txt")
    output_ass = os.path.join(PROCESSED_FOLDER, "output.ass")

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

    shutil.copy(ass_path, output_ass)

### Step 2: Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    print(f"🔹 Converting {input_mp4} to MP3...")
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)
    print(f"✅ MP3 saved at {output_mp3}")

### Step 3: Extract Required Chunks Based on Unclean File ###
def extract_required_chunks(mp3_path, unclean_file, segment_folder):
    os.makedirs(segment_folder, exist_ok=True)

    with open(unclean_file, "r", encoding="utf-8") as f:
        unclean_lines = f.readlines()

    segment_time = 5  # Optimize segment length per unclean line
    for idx, _ in enumerate(unclean_lines):
        output_segment = os.path.join(segment_folder, f"segment_{idx:03d}.mp3")
        subprocess.run(["ffmpeg", "-i", mp3_path, "-ss", str(idx * segment_time), "-t", str(segment_time), "-c", "copy", output_segment], check=True)

### Step 4: Run Whisper on Extracted Chunks (Optimized for Render Free-Tier) ###
def process_audio_for_timestamps(segment_folder):
    timestamps_file = os.path.join(PROCESSED_FOLDER, "timestamps.txt")
    final_srt_file = os.path.join(PROCESSED_FOLDER, "final.srt")

    def run_whisper(segment_path):
        print(f"🔹 Processing {segment_path} with Whisper...")
        return subprocess.run(["whisper", segment_path, "--model", "tiny", "--model_dir", WHISPER_CACHE_DIR], capture_output=True, text=True)

    threads = []
    MAX_CONCURRENT_THREADS = 3  # ✅ Balanced approach to avoid overloading Render CPU
    for idx, segment_file in enumerate(sorted(os.listdir(segment_folder))):
        segment_path = os.path.join(segment_folder, segment_file)
        thread = threading.Thread(target=run_whisper, args=(segment_path,))
        threads.append(thread)
        thread.start()

        if len(threads) >= MAX_CONCURRENT_THREADS:  
            for t in threads:
                t.join()
            threads.clear()  # ✅ Reset batch & start next batch

### Step 5: Cleanup Temporary Files ###
def cleanup(segment_folder, mp3_path):
    shutil.rmtree(segment_folder)
    os.remove(mp3_path)  # ✅ Delete MP3 after chunk extraction

@app.route('/')
def serve_index():
    return send_file(os.path.join(STATIC_FOLDER, "index.html"))

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'ass_file' not in request.files or 'mp4_file' not in request.files:
        return jsonify({"error": "Missing ASS or MP4 file"}), 400

    ass_file = request.files['ass_file']
    mp4_file = request.files['mp4_file']

    ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

    try:
        ass_file.save(ass_path)
        mp4_file.save(mp4_path)

        print("🔹 Extracting clean, unclean, and output.ass...")
        process_subtitles(ass_path)

        print("🔹 MP4 uploaded successfully. Converting to MP3...")
        convert_mp4_to_mp3(mp4_path, mp3_path)
        os.remove(mp4_path)  # ✅ Remove MP4 after MP3 is generated

    except Exception as e:
        return jsonify({"error": f"File save failed: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Files uploaded. Click 'Start Processing' to begin."}), 200

@app.route('/process', methods=['GET'])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
