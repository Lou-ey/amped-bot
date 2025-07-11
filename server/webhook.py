from flask import Flask, request
import subprocess

app = Flask(__name__)

@app.route('/update-amped', methods=['POST'])
def webhook():
    subprocess.Popen(["/bin/bash", "/home/luis/Projects/discord_bot/amped-bot/server/update.sh"])
    return "Update started!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
