import os
import shutil
import subprocess
import time
from flask import Flask, request, render_template, send_file, Response

app = Flask(__name__)

# Define base directory dynamically (works locally & on Render)
PY_DIR = os.path.dirname(os.path.abspath(__file__))

# Define output directory inside Render
OUTPUT_DIR = os.path.join(PY_DIR, "processed_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure it exists

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        print("Request Content-Type:", request.content_type)
        print("Received form data:", request.form)  # Debugging

        # Get uploaded files
        ass_file = request.files.get("ass_file")
        mp4_file = request.files.get("mp4_file")

        if not ass_file or not mp4_file:
            return "Error: Missing uploaded files!", 400

        # Define file paths with new fixed names
        ass_path = os.path.join(PY_DIR, "input.ass")
        mp4_path = os.path.join(PY_DIR, "input.mp4")

        # ✅ Rename and save uploaded files
        ass_file.save(ass_path)
        mp4_file.save(mp4_path)

        print("✅ Files uploaded and renamed: input.ass, input.mp4")

        # ✅ Ensure full upload by checking file size stability
        prev_size = 0
        while True:
            time.sleep(2)
            current_size = os.path.getsize(mp4_path)
            if current_size == prev_size:
                break
            prev_size = current_size

        print("✅ Files are fully uploaded. Proceeding to processing.")

        return render_template("processing.html")

    return render_template("index.html")  # ✅ Ensures GET requests show the upload form first

@app.route("/process")
def process():
    """Starts processing and stops execution on error."""
    try:
        result = subprocess.run(
            ["python", os.path.join(PY_DIR, "swearsfinder.py")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # ✅ Stop if an error occurs
        if result.returncode != 0:
            error_message = result.stderr.decode("utf-8")
            return f"❌ Processing failed! Error: {error_message}", 500

        print("Generated Files:", os.listdir(os.path.join(PY_DIR, "processed_output")))

        # Move output files to Render output directory
        output_files = ["output.ass", "final.srt", "clean.txt", "unclean.txt", "timestamps.txt"]
        download_links = []
        for file in output_files:
            source_path = os.path.join(PY_DIR, file)
            destination_path = os.path.join(OUTPUT_DIR, file)
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                download_links.append(file)

        return render_template("download.html", files=download_links)

    except Exception as e:
        return f"❌ Fatal error: {str(e)}", 500

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

@app.route("/stream")
def stream():
    """Stream script output live to the web page **only after processing starts**."""
    def generate_output():
        process = subprocess.Popen(
            ["python", os.path.join(PY_DIR, "swearsfinder.py")], 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        for line in iter(process.stdout.readline, b""):
            yield f"data: {line.decode('utf-8')}\n\n"

        error_output = process.stderr.read().decode("utf-8")
        if error_output:
            yield f"data: ❌ Error: {error_output}\n\n"

    return Response(generate_output(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
