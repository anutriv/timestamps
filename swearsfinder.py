import re
import os
import sys
import subprocess
import whisper
import nltk
from nltk.stem import WordNetLemmatizer
import ffmpeg  # ✅ Import ffmpeg-python

from flask import Flask, request, render_template

app = Flask(__name__)

# Define base directory dynamically (works locally & on Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check for required files
required_files = ["input.mp4", "input.ass"]
missing_files = [file for file in required_files if not os.path.exists(os.path.join(BASE_DIR, file))]

if missing_files:
    print(f"❌ Error: Missing required files: {', '.join(missing_files)}. Please upload them before running the script.")
    sys.exit(1)  # 🚀 Stops script execution if files are missing

print("✅ All required files are present. Proceeding with execution...")

# Install missing packages
REQUIRED_PACKAGES = ["nltk"]
def install_missing_packages():
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

install_missing_packages()
nltk.download('wordnet')

lemmatizer = WordNetLemmatizer()

EXCEPTIONS = {"as", "pass", "bass"}

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get uploaded files
        ass_file = request.files.get("ass_file")
        mp4_file = request.files.get("mp4_file")

        if not ass_file or not mp4_file:
            return "Error: Missing uploaded files!", 400

        # Define file paths with new fixed names
        ass_path = os.path.join(BASE_DIR, "input.ass")
        mp4_path = os.path.join(BASE_DIR, "input.mp4")

        # ✅ Rename and save uploaded files
        ass_file.save(ass_path)
        mp4_file.save(mp4_path)

        print("✅ Files uploaded and renamed: input.ass, input.mp4")

        return render_template("processing.html")

    return render_template("index.html")

def convert_mp4_to_mp3(input_mp4, output_mp3):
    ffmpeg.input(input_mp4).output(output_mp3, format='mp3', acodec='libmp3lame').run()

convert_mp4_to_mp3(os.path.join(BASE_DIR, "input.mp4"), os.path.join(BASE_DIR, "input.mp3"))

def extract_audio(input_audio, output_audio, start_time, end_time):
    ffmpeg.input(input_audio, ss=start_time, to=end_time).output(output_audio, format="mp3", acodec="libmp3lame").run()

def extract_audio_chunks(input_mp3, unclean_txt, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # ✅ Check if `unclean.txt` exists
    if not os.path.exists(unclean_txt):
        raise FileNotFoundError(f"❌ Error: '{unclean_txt}' not found. Ensure it is generated before processing.")

    with open(unclean_txt, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    audio_chunks = []
    for index, line in enumerate(lines):
        match = re.match(r'Dialogue: \d+,(.*?),(.*?),.*?,.*?,.*?,.*?,.*?,(.*)', line)
        if match:
            start_time, end_time, text = match.groups()
            start_seconds = timestamp_to_seconds(start_time)
            end_seconds = timestamp_to_seconds(end_time)
            
            chunk_path = os.path.join(output_dir, f"chunk_{index}.mp3")
            extract_audio(input_mp3, chunk_path, start_seconds, end_seconds)
            audio_chunks.append((chunk_path, text.strip(), start_seconds, end_seconds))

    return audio_chunks

audio_chunks = extract_audio_chunks(
    os.path.join(BASE_DIR, "input.mp3"),
    os.path.join(BASE_DIR, "unclean.txt"),
    os.path.join(BASE_DIR, "audio_chunks")
)

model = whisper.load_model("medium")
transcribe_audio_chunks(audio_chunks, model)

extract_matching_timestamps(
    os.path.join(BASE_DIR, "final.srt"),
    os.path.join(BASE_DIR, "swears.txt"),
    os.path.join(BASE_DIR, "timestamps.txt")
)

os.remove(os.path.join(BASE_DIR, "input.mp3"))
shutil.rmtree(os.path.join(BASE_DIR, "audio_chunks"))

print("✅ Cleanup complete! All temporary files deleted.")
print("✅ Processing complete!")
