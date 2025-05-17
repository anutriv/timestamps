import os
import shutil
import subprocess
from flask import Flask, request, render_template, send_file

app = Flask(__name__)

# ✅ Increase Flask’s request size limit (500MB)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB limit

# Define Render project directory
BASE_DIR = "/opt/render/project/src"

# File paths
input_ass = os.path.join(BASE_DIR, "input.ass")
input_mp4 = os.path.join(BASE_DIR, "input.mp4")
output_files = ["unclean.txt", "clean.txt", "final.srt", "output.ass", "timestamps.txt"]

@app.route("/")
def index():
    """Render the HTML upload form."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    """Handles file upload, renames them to `input.ass` and `input.mp4`."""
    ass_file = request.files.get("ass_file")
    mp4_file = request.files.get("mp4_file")

    if not ass_file or not mp4_file:
        return "❌ Error: Both files must be uploaded!", 400

    # Save files with fixed names
    ass_file.save(input_ass)
    mp4_file.save(input_mp4)

    print("✅ Files uploaded and renamed successfully.")
    return "✅ Upload Complete!", 200

@app.route("/process", methods=["GET"])
def process():
    """Runs `swearsfinder.py` script in Render."""
    try:
        result = subprocess.run(
            ["python", os.path.join(BASE_DIR, "swearsfinder.py")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        if result.returncode != 0:
            error_message = result.stderr.decode("utf-8")
            return f"❌ Processing failed!\n{error_message}", 500

        print("✅ Processing completed successfully!")
        return "✅ Processing complete!", 200

    except Exception as e:
        return f"❌ Fatal error: {str(e)}", 500

@app.route("/download/<filename>")
def download(filename):
    """Allows downloading of output files."""
    file_path = os.path.join(BASE_DIR, filename)

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "❌ File not found!", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
