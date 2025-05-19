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

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
STATIC_FOLDER = "static"
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

### Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    subprocess.run(["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3], check=True)

### Segment MP3 to Reduce Memory Usage ###
def segment_audio(mp3_path, segment_folder):
    os.makedirs(segment_folder, exist_ok=True)
    
    # ✅ Added file existence check to prevent errors
    if not os.path.exists(mp3_path):
        print(f"❌ Error: MP3 file '{mp3_path}' not found.")
        return False

    subprocess.run(["ffmpeg", "-i", mp3_path, "-f", "segment", "-segment_time", "30",
                    "-c", "copy", f"{segment_folder}/segment_%03d.mp3"], check=True)
    
    return True  # ✅ Indicate success

@app.route('/')
def serve_index():
    return send_file(os.path.join(STATIC_FOLDER, "index.html"))

def load_swears(file_path):
    """Loads swear words from a file, removing exceptions."""
    if not os.path.exists(file_path):
        print(f"⚠️ Warning: Swears file '{file_path}' not found!")
        return set()

    with open(file_path, 'r', encoding='utf-8') as file:
        return {line.strip().lower() for line in file if line.strip().lower() not in EXCEPTIONS}

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'ass_file' not in request.files or 'mp4_file' not in request.files:
        return jsonify({"error": "Missing ASS or MP4 file"}), 400

    ass_file = request.files['ass_file']
    mp4_file = request.files['mp4_file']

    ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
    mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")

    try:
        ass_file.save(ass_path)
        mp4_file.save(mp4_path)
    except Exception as e:
        return jsonify({"error": f"File save failed: {str(e)}"}), 500

    return jsonify({"success": True, "message": "Files uploaded successfully!"}), 200

def censor_ass_file(input_ass, swears_file, output_ass, clean_file, unclean_file):
    swears = load_swears(swears_file)
    with open(input_ass, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    censored_lines, affected_lines, original_affected_lines = [], [], []
    for line in lines:
        original_line = line  
        modified = False

        words = re.findall(r'\b\w+\b', line)
        for word in words:
            lemma_word = lemmatizer.lemmatize(word.lower(), pos='v')
            lemma_word_noun = lemmatizer.lemmatize(word.lower(), pos='n')

            if (lemma_word in swears or lemma_word_noun in swears) and word.lower() not in EXCEPTIONS:
                line = line.replace(word, word[0] + '.' * (len(word) - 1))
                modified = True

        censored_lines.append(line)
        if modified and line.startswith("Dialogue:"):
            affected_lines.append(line)
            original_affected_lines.append(original_line)

    with open(output_ass, 'w', encoding='utf-8') as file:
        file.writelines(censored_lines)
    with open(clean_file, 'w', encoding='utf-8') as file:
        file.writelines(affected_lines)
    with open(unclean_file, 'w', encoding='utf-8') as file:
        file.writelines(original_affected_lines)

def process_audio_for_timestamps(mp3_path):
    whisper_model = whisper.load_model("tiny")
    segment_folder = os.path.join(PROCESSED_FOLDER, "audio_segments")
    
    if segment_audio(mp3_path, segment_folder):  # ✅ Ensure segmentation is successful
        timestamps_file = os.path.join(PROCESSED_FOLDER, "timestamps.txt")
        final_srt_file = os.path.join(PROCESSED_FOLDER, "final.srt")

        with open(timestamps_file, "w", encoding="utf-8") as f, open(final_srt_file, "w", encoding="utf-8") as srt_f:
            for segment_file in sorted(os.listdir(segment_folder)):
                segment_path = os.path.join(segment_folder, segment_file)
                result = whisper_model.transcribe(segment_path)

                for i, segment in enumerate(result["segments"]):
                    f.write(f"{segment['start']} --> {segment['end']} {segment['text']}\n")
                    srt_f.write(f"{i+1}\n{segment['start']} --> {segment['end']}\n{segment['text']}\n\n")

        shutil.rmtree(segment_folder)

def async_process_files():
    global processing_status
    try:
        processing_status["completed"] = False
        mp4_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
        ass_path = os.path.join(UPLOAD_FOLDER, "input.ass")
        mp3_path = os.path.join(PROCESSED_FOLDER, "input.mp3")

        if os.path.exists(mp4_path):  # ✅ Prevents FFmpeg errors
            convert_mp4_to_mp3(mp4_path, mp3_path)
        else:
            print(f"❌ Error: MP4 file '{mp4_path}' not found.")
            return

        censor_ass_file(ass_path, "swears.txt", "processed/output.ass", "processed/clean.txt", "processed/unclean.txt")
        process_audio_for_timestamps(mp3_path)

        os.remove(mp3_path)
        processing_status["completed"] = True

    except Exception as e:
        processing_status["completed"] = False
        print(f"❌ Error in processing: {str(e)}")

@app.route('/process', methods=['GET'])
def process_files():
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
    app.run(host='0.0.0.0', port=5000)
