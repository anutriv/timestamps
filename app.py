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

# ✅ Allow requests from your Vercel frontend
CORS(app, resources={r"/*": {"origins": "https://timestamps-umber.vercel.app"}})

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
PROCESSED_FOLDER = os.path.join(os.getcwd(), "processed")
STATIC_FOLDER = os.path.join(os.getcwd(), "static")
VOSK_MODEL_PATH = os.path.join(os.getcwd(), "vosk-model")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB upload limit

processing_status = {"completed": False}

### 🔹 **Fix for NLTK Read-Only Issue**
NLTK_DATA_DIR = "/tmp/nltk_data"  # ✅ Use writable directory
os.makedirs(NLTK_DATA_DIR, exist_ok=True)  # Ensure `/tmp/nltk_data` exists

nltk.data.path.append(NLTK_DATA_DIR)
nltk.download("wordnet", download_dir=NLTK_DATA_DIR)

EXCEPTIONS = {"as", "pass", "bass"}
lemmatizer = nltk.stem.WordNetLemmatizer()

SWEAR_WORDS = ["damn", "hell", "shit", "fuck", "bitch", "bastard"]

### 🔹 **Automatic Vosk Model Download at Startup**
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

### 🔹 **Serve index.html at `/`**
@app.route("/")
def serve_index():
    return send_file(os.path.join(STATIC_FOLDER, "index.html"))

### 🔹 **✅ Fix for JSON Response in Upload Endpoint**
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

### 🔹 **✅ Handle Preflight CORS Requests**
@app.route("/upload", methods=["OPTIONS"])
def handle_preflight():
    response = jsonify({"message": "Preflight request handled"})
    response.headers["Access-Control-Allow-Origin"] = "https://timestamps-umber.vercel.app"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

### 🔹 **✅ Add CORS Headers for All Responses**
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "https://timestamps-umber.vercel.app"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

### **✅ Remove Explicit Port Settings (Vercel assigns it dynamically)**
if __name__ == "__main__":
    app.run()
