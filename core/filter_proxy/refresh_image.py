import eventlet
eventlet.monkey_patch()

import os
import json

from eventlet.websocket import WebSocketWSGI
from eventlet import wsgi
from eventlet.websocket import WebSocketWSGI
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from flask import Flask, request, jsonify



app = Flask(__name__)

# רשימת קליינטים מחוברים
clients = set()

# ---------- WebSocket handler ----------
def ws_handler(ws):
    clients.add(ws)
    print("WS client connected")

    try:
        while True:
            eventlet.sleep(999999)

    except Exception:
        pass
    finally:
        clients.discard(ws)
        print("WS client disconnected")


@app.route("/notify", methods=["POST"])
def notify():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    image_url = data.get("image_url")
    status = data.get("status")

    if not image_url or not status:
        return jsonify({"error": "Missing image_url or status"}), 400

    payload = json.dumps({
        "image_url": image_url,
        "status": status
    })

    dead = []
    for ws in clients:
        try:
            ws.send(payload)
        except Exception:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)

    print(f"Notify sent: {image_url} ({status})")
    return jsonify({"ok": True})


# ---------- Main ----------
if __name__ == "__main__":
    CERT_FILE = "ca/flask.crt"
    KEY_FILE = "ca/flask.key"

    listener = eventlet.wrap_ssl(
        eventlet.listen(("127.0.0.1", 8081)),
        certfile=CERT_FILE,
        keyfile=KEY_FILE,
        server_side=True,
    )

    # חיבור Flask + WebSocket באותו שרת
    application = DispatcherMiddleware(app, {
        "/ws": WebSocketWSGI(ws_handler)
    })

    print("WS server running on wss://127.0.0.1:8081/ws")
    wsgi.server(listener, application)
