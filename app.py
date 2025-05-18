import os
import re
import sys
import subprocess
import shutil
import whisper
import nltk
from nltk.stem import WordNetLemmatizer
from flask import Flask, request, jsonify
from flask_cors import CORS

# Flask Setup for Web Integration
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
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
        base_swears = {line.strip().lower() for line in file if line.strip().lower() not in EXCEPTIONS}
    expanded_swears = set(base_swears)
    for swear in base_swears:
        expanded_swears.add(lemmatizer.lemmatize(swear, pos='v'))
        expanded_swears.add(lemmatizer.lemmatize(swear, pos='n'))
    return expanded_swears

### Censor Swear Words in Subtitles ###
def censor_word(word):
    return word[0] + '.' * (len(word) - 1) if len(word) > 1 else word

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
                line = line.replace(word, censor_word(word))
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

### Extract Audio Timestamps ###
def timestamp_to_seconds(timestamp):
    h, m, s = map(float, timestamp.replace(',', '.').split(':'))
    return h * 3600 + m * 60 + s

def extract_audio(input_audio, output_audio, start_time, end_time):
    command = ["ffmpeg", "-i", input_audio, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", output_audio]
    subprocess.run(command, check=True)

def extract_audio_chunks(input_mp3, unclean_txt, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
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

### Transcribe Audio Using Whisper ###
def transcribe_audio_chunks(audio_chunks, model):
    srt_entries = []
    for index, (chunk_path, reference_text, start_time, end_time) in enumerate(audio_chunks):
        result = model.transcribe(chunk_path, language="en", word_timestamps=True)

        if "words" not in result:
            words = reference_fallback(reference_text, start_time, end_time)
        else:
            words = [(word["text"], start_time + word["start"], start_time + word["end"]) for word in result["words"]]

        srt_entries.extend([f"{index + i + 1}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{word}\n"
                            for i, (word, start, end) in enumerate(words)])
    
    with open("final.srt", 'w', encoding='utf-8') as file:
        file.writelines("\n".join(srt_entries))

### Extract Matching Timestamps for Swears ###
def extract_matching_timestamps(srt_file, swears_file, output_txt):
    swears = load_swears(swears_file)
    matching_timestamps = []

    with open(srt_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for i in range(len(lines)):
        if "-->" in lines[i]:
            timestamp_start, timestamp_end = lines[i].strip().split(" --> ")
            words = lines[i + 1].strip().split()

            for word in words:
                clean_word = re.sub(r'[^\w]', '', word).lower()
                if clean_word in swears:
                    matching_timestamps.append(f"{timestamp_start.replace(',', ':')} to {timestamp_end.replace(',', ':')}")

    with open(output_txt, 'w', encoding='utf-8') as file:
        file.writelines("\n".join(matching_timestamps))

### Execute Steps ###
convert_mp4_to_mp3("input.mp4", "input.mp3")
censor_ass_file("input.ass", "swears.txt", "output.ass", "clean.txt", "unclean.txt")
audio_chunks = extract_audio_chunks("input.mp3", "unclean.txt", "audio_chunks")
model = whisper.load_model("medium")
transcribe_audio_chunks(audio_chunks, model)
extract_matching_timestamps("final.srt", "swears.txt", "timestamps.txt")

### Clean Up Temporary Files ###
shutil.rmtree("audio_chunks")
os.remove("input.mp3")

print("Processing complete! All temporary files have been deleted.")
