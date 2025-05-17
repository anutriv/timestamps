import re
import os
import sys
import subprocess
import whisper
import nltk
from nltk.stem import WordNetLemmatizer
import shutil

BASE_DIR = "/opt/render/project/src"

# Define file paths dynamically
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

def run_swearsfinder():
    """Runs the entire processing flow."""
    convert_mp4_to_mp3(input_mp4, input_mp3)
    censor_ass_file(input_ass, swears_txt, output_ass, clean_txt, unclean_txt)
    audio_chunks = extract_audio_chunks(input_mp3, unclean_txt, audio_chunks_dir)
    model = whisper.load_model("medium")
    transcribe_audio_chunks(audio_chunks, model)
    extract_matching_timestamps(final_srt, swears_txt, timestamps_txt)

    # Clean up temporary files
    os.remove(input_mp3)
    shutil.rmtree(audio_chunks_dir)

    print("✅ Processing complete!")
    return "Processing complete!"

# ✅ No longer auto-executes—now runs via Flask when called.
