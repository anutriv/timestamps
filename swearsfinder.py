import re
import os
import sys
import subprocess
import whisper
import nltk
from nltk.stem import WordNetLemmatizer
import ffmpeg  # ✅ Import ffmpeg-python instead of PyAudio

# Required packages
REQUIRED_PACKAGES = ["nltk"]

# Function to check and install missing Python packages
def install_missing_packages():
    """Check for required Python packages and install missing ones."""
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

# Ensure NLTK resources are available
def setup_nltk():
    """Ensure NLTK resources are downloaded."""
    nltk.download('wordnet')

# Perform setup
install_missing_packages()
setup_nltk()

# Initialize lemmatizer
lemmatizer = WordNetLemmatizer()

# Define exceptions for words that should NOT be censored
EXCEPTIONS = {"as", "pass", "bass"}

# Define base directory dynamically (works locally & on Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

### Convert input.mp4 to input.mp3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    """Converts MP4 video to MP3 audio using FFmpeg."""
    ffmpeg.input(input_mp4).output(output_mp3, format='mp3', acodec='libmp3lame').run()

# Convert the video before proceeding with other steps
convert_mp4_to_mp3(os.path.join(BASE_DIR, "input.mp4"), os.path.join(BASE_DIR, "input.mp3"))

### Extract audio chunks using FFmpeg ###
def extract_audio(input_audio, output_audio, start_time, end_time):
    """Extracts a specific time segment from the audio file using FFmpeg."""
    ffmpeg.input(input_audio, ss=start_time, to=end_time).output(output_audio, format="mp3", acodec="libmp3lame").run()

### Extract and transcribe audio chunks ###
def extract_audio_chunks(input_mp3, unclean_txt, output_dir):
    """Extracts individual audio chunks based on timestamps in unclean.txt using FFmpeg."""
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

# Use dynamic paths
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

# Clean up temporary files
os.remove(os.path.join(BASE_DIR, "input.mp3"))  # Delete MP3 file
shutil.rmtree(os.path.join(BASE_DIR, "audio_chunks"))  # Remove folder

print("Cleanup complete! All temporary files have been deleted.")
print("Processing complete!")
