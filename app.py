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

### Step 4: Run Whisper on Extracted Chunks ###
def process_audio_for_timestamps(segment_folder):
    timestamps_file = os.path.join(PROCESSED_FOLDER, "timestamps.txt")
    final_srt_file = os.path.join(PROCESSED_FOLDER, "final.srt")

    with open(timestamps_file, "w", encoding="utf-8") as f, open(final_srt_file, "w", encoding="utf-8") as srt_f:
        for segment_file in sorted(os.listdir(segment_folder)):
            segment_path = os.path.join(segment_folder, segment_file)
            print(f"🔹 Processing {segment_file} with Whisper...")
            result = subprocess.run(["whisper", segment_path, "--model", "tiny"], capture_output=True, text=True)

            if result.returncode == 0:
                transcribed_text = result.stdout.strip()
                f.write(f"{segment_file} {transcribed_text}\n")
                srt_f.write(f"{segment_file}\n{transcribed_text}\n\n")
            else:
                print(f"❌ Whisper failed for {segment_file}. Error:\n{result.stderr}")

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

    return jsonify({"success": True, "message": "Files uploaded & processed!"}), 200

def async_process_files():
    global processing_status
    try:
        processing_status["completed"] = False
        mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")
        unclean_file = os.path.join(PROCESSED_FOLDER, "unclean.txt")
        segment_folder = os.path.join(PROCESSED_FOLDER, "audio_segments")

        print("🔹 Extracting required chunks...")
        extract_required_chunks(mp3_path, unclean_file, segment_folder)
        os.remove(mp3_path)  # ✅ Delete MP3 after extracting chunks

        process_audio_for_timestamps(segment_folder)
        cleanup(segment_folder, mp3_path)  # ✅ Final cleanup

        processing_status["completed"] = True

    except Exception as e:
        processing_status["completed"] = False
        print(f"❌ Error in processing: {str(e)}")

@app.route('/process', methods=['GET'])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
