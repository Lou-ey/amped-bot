from flask import Flask, request, abort
import subprocess
import os

app = Flask(__name__)

SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN')

@app.route('/update-amped', methods=['POST'])
def webhook():
    token = request.headers.get('X-Auth-Token')
    if token != SECRET_TOKEN:
        abort(403)  # Forbidden if token does not match

    subprocess.Popen(["/bin/bash", "/home/user/amped-bot/server/update.sh"])
    return "Update started!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
