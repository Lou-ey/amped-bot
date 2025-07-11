from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route('/github-webhook', methods=['POST'])
def webhook():
    subprocess.Popen(["/bin/bash", "./update.sh"])
    return "✅ Update started!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
