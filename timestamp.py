import os
import shutil
from flask import Flask, request, render_template, send_file

app = Flask(__name__)

# Define base directory dynamically (works locally & on Render)
PY_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get uploaded files
        ass_file = request.files["ass_file"]
        mp4_file = request.files["mp4_file"]
        output_folder = request.form.get("output_folder").strip()

        # Validate folder path
        if not output_folder:
            return "Invalid directory path. Please enter a valid folder.", 400

        # Ensure the output directory exists
        os.makedirs(output_folder, exist_ok=True)

        # Save uploaded files
        ass_file.save(os.path.join(PY_DIR, "input.ass"))
        mp4_file.save(os.path.join(PY_DIR, "input.mp4"))

        # Run the processing script
        os.system(f"python {os.path.join(PY_DIR, 'swearsfinder.py')}")

        # Move output files to the selected directory
        output_files = ["output.ass", "final.srt", "clean.txt", "unclean.txt", "timestamps.txt"]
        download_links = []
        for file in output_files:
            source_path = os.path.join(PY_DIR, file)
            destination_path = os.path.join(output_folder, file)
            if os.path.exists(source_path):
                shutil.move(source_path, destination_path)
                download_links.append(file)

        return render_template("download.html", files=output_files)


    return render_template("index.html")  # Render the upload form

@app.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(PY_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "File not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
