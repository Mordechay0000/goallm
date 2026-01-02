# flask server code
import os
import eventlet.wsgi
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO

# אתחול אפליקציית Flask
app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your_very_secret_key_here!' # מומלץ להוסיף בסביבת Production

# אתחול SocketIO
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

# --- Routes ---

@app.route('/static/<path:filename>')
def serve_static(filename: str):
    """מגיש קבצים סטטיים מהתיקייה 'static'."""
    return send_from_directory('static', filename)

@app.route('/notify', methods=['POST'])
def notify():
    """
    מקבל הודעות (סטטוס עיבוד תמונה + URL) דרך POST
    ומשדר את ה-URL והסטטוס ללקוחות SocketIO.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    # קבלת הנתונים מהבקשה
    image_hash = data.get('image_hash') # עדיין יכול להגיע מ-mitmproxy
    image_url = data.get('image_url')   # <-- הנתון החדש והחשוב לקליינט
    status = data.get('status')

    # !!! בדיקת תקינות - ודא שגם URL וגם סטטוס קיימים !!!
    if not image_url or not status:
        # אפשר להוסיף בדיקה גם ל-image_hash אם משתמשים בו ללוגים
        return jsonify({"error": "Missing 'image_url' or 'status' in JSON payload"}), 400

    # הדפסת לוג עם ה-URL (וה-hash אם רוצים)
    log_message = f"Received notification: url={image_url}, status={status}"
    if image_hash:
        log_message += f" (hash={image_hash})"
    print(log_message)

    # !!! שידור ה-URL והסטטוס ללקוחות !!!
    socketio.emit('image_update', {'image_url': image_url, 'status': status})

    return jsonify({'status': 'ok'}), 200

# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

# --- Main Execution ---
if __name__ == '__main__':
    CERT_FILE = '../../ca/flask.crt'
    KEY_FILE = '../../ca/flask.key'

    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        print(f"Error: SSL certificate ('{CERT_FILE}') or key ('{KEY_FILE}') not found.")
        print("Please ensure the certificate and key files are in the correct location.")
        exit(1)

    ssl_args = {
        'certfile': CERT_FILE,
        'keyfile': KEY_FILE
    }

    print(f"Starting server on https://127.0.0.1:8081")
    print("Using eventlet with SSL.")

    try:
        listener = eventlet.wrap_ssl(
            eventlet.listen(('127.0.0.1', 8081)),
            **ssl_args,
            server_side=True
        )
        eventlet.wsgi.server(
            listener,
            app,
            log_output=True
        )
    except Exception as e:
        print(f"Failed to start server: {e}")
        exit(1)