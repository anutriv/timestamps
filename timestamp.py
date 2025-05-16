import os
import shutil
import tkinter as tk
from tkinter import filedialog
from flask import Flask, request, render_template

app = Flask(__name__)

# Function to open a folder selection dialog
def select_folder():
    root = tk.Tk()
    root.withdraw()  # Hide the Tkinter window
    folder_selected = filedialog.askdirectory(title="Select Output Folder")  # Open folder picker
    return folder_selected

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        ass_file = request.files["ass_file"]  # Get uploaded ASS file
        mp4_file = request.files["mp4_file"]  # Get uploaded MP4 file
        
        py_dir = "D:/cleanfile/TIMESTAMP"  # Python script directory

        # Use Tkinter to select the output folder dynamically
        ass_dir = request.form.get("output_folder").strip()

        # Debugging output
        print(f"Selected ASS file directory: {ass_dir}")

        # Validate the folder path
        if not ass_dir or not os.path.isdir(ass_dir):
            print("Error: Invalid ASS directory provided!")
            return "Invalid directory path. Please select a valid folder.", 400  # Proper error response

        # Define paths for saving files in Python directory
        saved_ass_path = os.path.join(py_dir, "input.ass")
        saved_mp4_path = os.path.join(py_dir, "input.mp4")

        # Save uploaded files in Python directory
        ass_file.save(saved_ass_path)
        mp4_file.save(saved_mp4_path)

        print(f"User-selected folder for output: {ass_dir}")

        # Ensure directory exists
        if not os.path.exists(ass_dir):
            print(f"Creating directory: {ass_dir}")
            os.makedirs(ass_dir)  # Create the directory if missing

        # Run the Python script
        os.system(f"python {os.path.join(py_dir, 'swearsfinder.py')}")

        # Move generated output files dynamically
        output_files = ["output.ass", "final.srt", "clean.txt", "unclean.txt", "timestamps.txt"]
        
        for file in output_files:
            source_path = os.path.join(py_dir, file)
            destination_path = os.path.join(ass_dir, file)

            print(f"Checking: {source_path} -> {destination_path}")
            
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                print(f"Moved {source_path} -> {destination_path}")
            else:
                print(f"Warning: {source_path} not found. Skipping...")

        return "Processing Complete!"  # Final response after completion

    return render_template("index.html")  # Render the web page for GET requests

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)

