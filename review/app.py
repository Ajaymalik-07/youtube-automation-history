"""
Review Server
Spins up a local Flask web app so you can watch the video,
read the script, and approve or reject before uploading.
Phase 12 Overhaul: Replaced unsafe os.kill with cooperative Werkzeug shutdown,
and records human approval tokens in the uploader safety database.
"""
import os
import json
import threading
import webbrowser
import time
from flask import Flask, render_template, jsonify, request, send_file, abort
from werkzeug.serving import make_server
import config
from uploader.safety import (
    record_production_state,
    get_production_record,
    PublishingState,
)

app = Flask(__name__, template_folder="templates")

# Shared state (set before server starts)
_state = {
    "review_data": {},
    "decision": None,     # "approved" | "rejected"
}
_server = None


class ServerThread(threading.Thread):
    """Clean daemon server thread using werkzeug make_server for non-destructive shutdown."""
    def __init__(self, flask_app, port):
        super().__init__()
        self.server = make_server("127.0.0.1", port, flask_app)
        self.ctx = flask_app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


@app.route("/")
def index():
    return render_template("review.html")


@app.route("/api/data")
def get_data():
    data = _state["review_data"]
    # Strip the video path from JSON (serve it via /video endpoint instead)
    safe = {k: v for k, v in data.items() if k != "video_path"}
    return jsonify(safe)


@app.route("/video")
def serve_video():
    path = _state["review_data"].get("video_path", "")
    if path and os.path.exists(path):
        return send_file(path, mimetype="video/mp4")
    abort(404)


@app.route("/api/quality-report")
def quality_report():
    video_path = _state["review_data"].get("video_path", "")
    rec = get_production_record(video_path) if video_path else None
    q_gate = (rec or {}).get("quality_gate") or {}
    return jsonify({"ok": True, "report": q_gate, "state": (rec or {}).get("current_state")})


@app.route("/api/approve", methods=["POST"])
def approve():
    _state["decision"] = "approved"
    video_path = _state["review_data"].get("video_path", "")
    req_json = request.get_json(silent=True) or {}
    reviewer = req_json.get("reviewer", "automated_editor")
    notes = req_json.get("notes", "Confirmed via dashboard inspection")

    if video_path:
        record_production_state(
            video_path,
            PublishingState.UPLOAD_QUEUED.value,
            metadata={"editorial_inspection": {"reviewer": reviewer, "notes": notes}}
        )

    # Cooperative shutdown gives browser time to render confirmation banner
    threading.Timer(0.8, _shutdown).start()
    return jsonify({"status": "approved"})


@app.route("/api/reject", methods=["POST"])
def reject():
    _state["decision"] = "rejected"
    video_path = _state["review_data"].get("video_path", "")
    req_json = request.get_json(silent=True) or {}
    reason = req_json.get("reason", "Rejected via dashboard inspection")

    if video_path:
        record_production_state(
            video_path,
            PublishingState.BLOCKED_QUALITY_GATE.value,
            metadata={"rejection_reason": reason}
        )

    threading.Timer(0.8, _shutdown).start()
    return jsonify({"status": "rejected"})


def _shutdown():
    """Graceful shutdown without killing the host process."""
    global _server
    if _server:
        _server.shutdown()


def start_review_server(review_data: dict) -> bool:
    """
    Saves review data, starts Flask, opens the browser, and blocks
    until the user clicks Approve or Reject.
    Returns True if approved, False if rejected.
    """
    global _server
    _state["review_data"] = review_data
    _state["decision"] = None

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{config.REVIEW_PORT}")

    threading.Thread(target=open_browser, daemon=True).start()
    print(f"   → Review dashboard ready at http://localhost:{config.REVIEW_PORT}")

    _server = ServerThread(app, config.REVIEW_PORT)
    _server.start()
    _server.join()

    return _state.get("decision") == "approved"

