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
VOSK_MODEL_PATH = os.path.join(os.getcwd(), "vosk-model")  # ✅ Ensure manual placement of Vosk model
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

### Step 1: Extract Clean, Unclean & Output.ass ###
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

### Step 2: Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    print(f"🔹 Converting {input_mp4} to MP3...")
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)
    print(f"✅ MP3 saved at {output_mp3}")

### Step 3: Extract Required Chunks Based on Clean File ###
def extract_required_chunks(mp3_path, clean_file, segment_folder):
    os.makedirs(segment_folder, exist_ok=True)

    with open(clean_file, "r", encoding="utf-8") as f:
        clean_lines = f.readlines()

    segment_time = 5  # Optimize segment length per clean line
    for idx, _ in enumerate(clean_lines):
        output_segment = os.path.join(segment_folder, f"segment_{idx:03d}.wav")
        subprocess.run(["ffmpeg", "-i", mp3_path, "-ss", str(idx * segment_time), "-t", str(segment_time), "-ac", "1", "-ar", "16000", output_segment], check=True)

### Step 4: Run Vosk on Extracted Chunks ###
def process_audio_for_word_timestamps(segment_folder):
    model = Model(VOSK_MODEL_PATH)
    word_timestamps = {}
    srt_data = {}

    for segment_file in sorted(os.listdir(segment_folder)):
        segment_path = os.path.join(segment_folder, segment_file)
        wf = wave.open(segment_path, "rb")

        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)  # ✅ Enable word-level timing

        srt_output = []
        swear_timestamps = []

        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                for word in result["result"]:
                    start_time = round(word["start"], 2)
                    end_time = round(word["end"], 2)
                    srt_output.append(f"{start_time:.2f} --> {end_time:.2f}\n{word['word']}\n")

                    if word["word"].lower() in SWEAR_WORDS:  # ✅ Capture swear words timing
                        swear_timestamps.append(f"{start_time:.2f} --> {end_time:.2f}")

        srt_data[segment_file] = "\n".join(srt_output)
        word_timestamps[segment_file] = swear_timestamps

    # ✅ Generate final timestamp file for swear words
    swear_timestamp_file = os.path.join(PROCESSED_FOLDER, "swear_timestamps.txt")
    with open(swear_timestamp_file, "w", encoding="utf-8") as f:
        for timestamps in word_timestamps.values():
            f.write("\n".join(timestamps) + "\n")

    return srt_data, swear_timestamp_file

### Step 5: Cleanup Temporary Files ###
def cleanup(segment_folder, mp3_path):
    shutil.rmtree(segment_folder)
    os.remove(mp3_path)  # ✅ Delete MP3 after chunk extraction

### ✅ Fixed `async_process_files` definition BEFORE it's referenced ###
def async_process_files():
    global processing_status
    try:
        processing_status["completed"] = False
        mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")
        clean_file = os.path.join(PROCESSED_FOLDER, "clean.txt")
        segment_folder = os.path.join(PROCESSED_FOLDER, "audio_segments")

        print("🔹 Extracting required chunks...")
        extract_required_chunks(mp3_path, clean_file, segment_folder)
        os.remove(mp3_path)  # ✅ Delete MP3 after extracting chunks

        srt_data, swear_timestamp_file = process_audio_for_word_timestamps(segment_folder)
        cleanup(segment_folder, mp3_path)  # ✅ Final cleanup

        processing_status["completed"] = True

    except Exception as e:
        processing_status["completed"] = False
        print(f"❌ Error in processing: {str(e)}")

@app.route("/process", methods=["GET"])
def process_files():
    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
