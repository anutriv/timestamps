import re
import os
import sys
import subprocess
import whisper
import nltk
from nltk.stem import WordNetLemmatizer

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

### Convert input.mp4 to input.mp3 ###
def convert_mp4_to_mp3(input_mp4, output_mp3):
    """Converts MP4 video to MP3 audio using FFmpeg."""
    command = ["ffmpeg", "-i", input_mp4, "-q:a", "0", "-map", "a", output_mp3]
    subprocess.run(command, check=True)

# Convert the video before proceeding with other steps
convert_mp4_to_mp3("input.mp4", "input.mp3")

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

### Step 2: Extract and transcribe audio chunks
def timestamp_to_seconds(timestamp):
    """Convert timestamp format hh:mm:ss.ms to seconds."""
    h, m, s = map(float, timestamp.replace(',', '.').split(':'))
    return h * 3600 + m * 60 + s

def format_srt_timestamp(seconds):
    """Format seconds into SRT timestamp (hh:mm:ss,ms)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hours:02}:{minutes:02}:{sec:02},{ms:03}"

def extract_audio(input_audio, output_audio, start_time, end_time):
    """Extracts a specific time segment from the audio file."""
    command = [
        "ffmpeg",
        "-i", input_audio,
        "-ss", str(start_time),
        "-to", str(end_time),
        "-c", "copy",  # Copy codec to avoid re-encoding
        output_audio
    ]
    subprocess.run(command, check=True)

def extract_audio_chunks(input_mp3, unclean_txt, output_dir):
    """Extracts individual audio chunks based on timestamps in unclean.txt."""
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

def transcribe_audio_chunks(audio_chunks, model):
    """Transcribes audio chunks and generates a single .srt file."""
    srt_entries = []

    for index, (chunk_path, reference_text, start_time, end_time) in enumerate(audio_chunks):
        result = model.transcribe(chunk_path, language="en", word_timestamps=True)

        if "words" not in result:
            words = reference_fallback(reference_text, start_time, end_time)
        else:
            words = adjust_word_timestamps(result["words"], start_time, end_time)

        srt_entries.extend(generate_srt_entries(words, index))

    save_srt_file("final.srt", srt_entries)

def adjust_word_timestamps(words, start_time, end_time):
    return [(word["text"], format_srt_timestamp(start_time + word["start"]), format_srt_timestamp(start_time + word["end"])) for word in words]

def reference_fallback(reference_text, start_time, end_time):
    words = reference_text.split()
    time_step = (end_time - start_time) / max(len(words), 1)
    return [(word, format_srt_timestamp(start_time + i * time_step), format_srt_timestamp(start_time + (i + 1) * time_step)) for i, word in enumerate(words)]

def generate_srt_entries(words, index):
    return [f"{index + i + 1}\n{start} --> {end}\n{word}\n" for i, (word, start, end) in enumerate(words)]

def save_srt_file(srt_path, srt_entries):
    with open(srt_path, 'w', encoding='utf-8') as file:
        file.writelines("\n".join(srt_entries))

### Step 3: Extract swear word timestamps from final.srt
def extract_matching_timestamps(srt_file, swears_file, output_txt):
    """Extract timestamps of swear words from the final subtitle file in (mm:ss:ms to mm:ss:ms) format."""
    swears = load_swears(swears_file)
    matching_timestamps = []

    with open(srt_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for i in range(len(lines)):
        if "-->" in lines[i]:
            timestamp_start, timestamp_end = lines[i].strip().split(" --> ")
            words = lines[i + 1].strip().split()

            for word in words:
                clean_word = re.sub(r"[^\w']", '', word).lower()
                lemma_word = lemmatizer.lemmatize(clean_word, pos='n')

                if lemma_word in swears:
                    start_time = ":".join(timestamp_start.split(":")[1:]).replace(",", ":")
                    end_time = ":".join(timestamp_end.split(":")[1:]).replace(",", ":")
                    matching_timestamps.append(f"{start_time} to {end_time}")

    with open(output_txt, 'w', encoding='utf-8') as file:
        file.writelines("\n".join(matching_timestamps))
        

# Execute steps
censor_ass_file("input.ass", "swears.txt", "output.ass", "clean.txt", "unclean.txt")
audio_chunks = extract_audio_chunks("input.mp3", "unclean.txt", "audio_chunks")
model = whisper.load_model("medium")
transcribe_audio_chunks(audio_chunks, model)
extract_matching_timestamps("final.srt", "swears.txt", "timestamps.txt")

print("Processing complete!")
