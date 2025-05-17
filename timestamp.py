import os
import shutil
import subprocess
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
        # Debugging: Print request content type
        print("Request Content-Type:", request.content_type)
        print("Received form data:", request.form)  # Debugging: Print received form data

        # Get uploaded files
        ass_file = request.files.get("ass_file")
        mp4_file = request.files.get("mp4_file")

        if not ass_file or not mp4_file:
            return "Error: Missing uploaded files!", 400

        # Save uploaded files
        ass_file.save(os.path.join(PY_DIR, "input.ass"))
        mp4_file.save(os.path.join(PY_DIR, "input.mp4"))

        # ✅ Redirect to processing page instead of running script immediately
        return render_template("processing.html")  

    return render_template("index.html")  # Render the upload form

@app.route("/process")
def process():
    """Starts processing and moves files."""
    # Run the processing script
    os.system(f"python {os.path.join(PY_DIR, 'swearsfinder.py')}")

    # Debugging: Check generated files in Render
    print("Generated Files:", os.listdir(os.path.join(PY_DIR, "processed_output")))

    # Move output files to the Render output directory
    output_files = ["output.ass", "final.srt", "clean.txt", "unclean.txt", "timestamps.txt"]
    download_links = []
    for file in output_files:
        source_path = os.path.join(PY_DIR, file)
        destination_path = os.path.join(OUTPUT_DIR, file)
        if os.path.exists(source_path):
            shutil.move(source_path, destination_path)
            download_links.append(file)

    return render_template("download.html", files=download_links)  # ✅ Fix variable name

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
        process = subprocess.Popen(["python", os.path.join(PY_DIR, "swearsfinder.py")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(process.stdout.readline, b""):
            yield f"data: {line.decode('utf-8')}\n\n"

    return Response(generate_output(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
