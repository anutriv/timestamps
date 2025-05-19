import os
import re
import sys
import subprocess
import shutil
import nltk
import threading
import time
import wishper
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

### Convert MP4 to MP3 (Immediately Upon Upload) ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    print(f"🔹 Converting {input_mp4} to MP3...")
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)
    print(f"✅ MP3 saved at {output_mp3}")

### Segment MP3 to Reduce Memory Usage ###
def segment_audio(mp3_path, segment_folder):
    os.makedirs(segment_folder, exist_ok=True)
    
    if not os.path.exists(mp3_path):
        print(f"❌ Error: MP3 file '{mp3_path}' not found.")
        return False

    result = subprocess.run(["ffmpeg", "-i", mp3_path, "-f", "segment", "-segment_time", "30",
                             "-c", "copy", f"{segment_folder}/segment_%03d.mp3"], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ FFmpeg segmentation error: {result.stderr}")
        return False

    return True  

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

        time.sleep(2)  # ✅ Wait for files to be fully saved
        if not os.path.exists(mp4_path) or not os.path.exists(ass_path):
            return jsonify({"error": "File save failed. Check server permissions."}), 500

        print("🔹 MP4 uploaded successfully. Converting to MP3...")
        convert_mp4_to_mp3(mp4_path, mp3_path)
        
        if os.path.exists(mp3_path):  
            print("✅ MP3 conversion successful! Deleting MP4...")
            os.remove(mp4_path)  # ✅ Remove MP4 after MP3 is generated

        subprocess.run(["chmod", "-R", "777", UPLOAD_FOLDER], check=True)

    except Exception as e:
        return jsonify({"error": f"File save failed: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Files uploaded & MP4 converted to MP3!"}), 200

### Whisper Transcription Runs Externally ###
whisper_model = whisper.load_model("tiny")
def process_audio_for_timestamps(mp3_path):
    segment_folder = os.path.join(PROCESSED_FOLDER, "audio_segments")

    if segment_audio(mp3_path, segment_folder):
        timestamps_file = os.path.join(PROCESSED_FOLDER, "timestamps.txt")
        final_srt_file = os.path.join(PROCESSED_FOLDER, "final.srt")

        with open(timestamps_file, "w", encoding="utf-8") as f, open(final_srt_file, "w", encoding="utf-8") as srt_f:
            for segment_file in sorted(os.listdir(segment_folder)):
                segment_path = os.path.join(segment_folder, segment_file)

                print(f"🔹 Processing {segment_file} with Whisper...")
                result = subprocess.run(["whisper", segment_path, "--model", "tiny", "--model_dir", "whisper_models"], capture_output=True, text=True)

                if result.returncode == 0:
                    transcribed_text = result.stdout.strip()
                    f.write(f"{segment_file} {transcribed_text}\n")
                    srt_f.write(f"{segment_file}\n{transcribed_text}\n\n")
                else:
                    print(f"❌ Whisper failed for {segment_file}. Error:\n{result.stderr}")

        shutil.rmtree(segment_folder)  # ✅ Cleanup audio segments

def async_process_files():
    global processing_status
    try:
        processing_status["completed"] = False
        mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

        if os.path.exists(mp3_path):  
            process_audio_for_timestamps(mp3_path)
            os.remove(mp3_path)  # ✅ Delete MP3 after processing

        processing_status["completed"] = True

    except Exception as e:
        processing_status["completed"] = False
        print(f"❌ Error in processing: {str(e)}")

@app.route('/process', methods=['GET'])
def process_files():
    mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

    if not os.path.exists(mp3_path):
        return jsonify({"error": "Processing failed: MP3 file not found."}), 500

    threading.Thread(target=async_process_files).start()
    return jsonify({"message": "Processing started"}), 202

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({"status": "completed" if processing_status["completed"] else "in_progress"})

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not found or empty"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
