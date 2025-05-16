import subprocess
import webbrowser
import time

# Start the Flask server
flask_process = subprocess.Popen(["python", "timestamp.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Wait a few seconds for the server to fully initialize
time.sleep(3)

# Open the web page automatically
webbrowser.open("http://127.0.0.1:5000")

print("Flask server started successfully! Web browser opened.")
