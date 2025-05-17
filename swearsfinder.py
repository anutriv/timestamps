import re
import os
import sys
import subprocess
import whisper
import nltk
from nltk.stem import WordNetLemmatizer

# ✅ Define paths for Render deployment
BASE_DIR = "/opt/render/project/src"  # Render's project directory

# Define file paths dynamically for Render execution
input_ass = os.path.join(BASE_DIR, "input.ass")
input_mp4 = os.path.join(BASE_DIR, "input.mp4")
input_mp3 = os.path.join(BASE_DIR, "input.mp3")
swears_txt = os.path.join(BASE_DIR, "swears.txt")
output_ass = os.path.join(BASE_DIR, "output.ass")
clean_txt = os.path.join(BASE_DIR, "clean.txt")
unclean_txt = os.path.join(BASE_DIR, "unclean.txt")
final_srt = os.path.join(BASE_DIR, "final.srt")
timestamps_txt = os.path.join(BASE_DIR, "timestamps.txt")
audio_chunks_dir = os.path.join(BASE_DIR, "audio_chunks")

# Required packages
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

### Convert MP4 to MP3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    """Converts MP4 to MP3 using FFmpeg via subprocess."""
    command = ["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3]
    subprocess.run(command, check=True)

convert_mp4_to_mp3(input_mp4, input_mp3)

### Step 1: Censor swear words in .ass file ###
def load_swears(file_path):
    """Load swear words from file into a set, storing tense and plural variations, excluding exceptions."""
    with open(file_path, 'r', encoding='utf-8') as file:
        base_swears = {line.strip().lower() for line in file if line.strip().lower() not in EXCEPTIONS}
    
    expanded_swears = set(base_swears)

    for swear in base_swears:
        expanded_swears.add(lemmatizer.lemmatize(swear, pos='v'))  # Verb form (handles past/present)
        expanded_swears.add(lemmatizer.lemmatize(swear, pos='n'))  # Noun form (handles plural)

    return expanded_swears

def censor_word(word):
    """Censor a word by keeping the first letter and replacing the rest with dots."""
    return word[0] + '.' * (len(word) - 1) if len(word) > 1 else word

def censor_ass_file(input_ass, swears_file, output_ass, clean_file, unclean_file):
    """Scan the .ass file, replace swear words including plural and tense variations, and save affected lines."""
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
                censored_word = censor_word(word)
                line = line.replace(word, censored_word)  
                modified = True

        censored_lines.append(line)

        if modified and line.startswith("Dialogue:"):
            affected_lines.append(line)
            original_affected_lines.append(original_line)

    # Save results
    with open(output_ass, 'w', encoding='utf-8') as file:
        file.writelines(censored_lines)

    with open(clean_file, 'w', encoding='utf-8') as file:
        file.writelines(affected_lines)

    with open(unclean_file, 'w', encoding='utf-8') as file:
        file.writelines(original_affected_lines)

### Step 2: Extract and transcribe audio chunks ###
def timestamp_to_seconds(timestamp):
    """Convert timestamp format hh:mm:ss.ms to seconds."""
    h, m, s = map(float, timestamp.replace(',', '.').split(':'))
    return h * 3600 + m * 60 + s

def extract_audio(input_audio, output_audio, start_time, end_time):
    """Extracts a specific time segment from the audio file."""
    command = ["ffmpeg", "-i", input_audio, "-ss", str(start_time), "-to", str(end_time), "-c", "copy", output_audio]
    subprocess.run(command, check=True)

def extract_audio_chunks(input_mp3, unclean_txt, output_dir):
    """Extracts individual audio chunks based on timestamps."""
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

model = whisper.load_model("medium")
audio_chunks = extract_audio_chunks(input_mp3, unclean_txt, audio_chunks_dir)
transcribe_audio_chunks(audio_chunks, model)

### Step 3: Extract swear word timestamps ###
extract_matching_timestamps(final_srt, swears_txt, timestamps_txt)

### Clean Up Temporary Files ###
os.remove(input_mp3)
shutil.rmtree(audio_chunks_dir)

print("Cleanup complete! All temporary files have been deleted.")
print("Processing complete!")
