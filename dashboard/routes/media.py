from flask import Blueprint, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime
import json
import threading
import uuid

bp = Blueprint("media", __name__, url_prefix="/media")

MEDIA_DIR     = Path("client/media")
PROCESSED_DIR = Path("client/media/processed")
QUEUE_DIR     = Path("client/media/queue")
ALLOWED_EXT   = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".webp"}


def _all_media():
    items = []
    for f in sorted(MEDIA_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() in ALLOWED_EXT:
            sidecar = f.with_suffix(".json")
            meta = {}
            if sidecar.exists():
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                except Exception:
                    pass
            items.append({"filename": f.name, "path": str(f), "meta": meta})
    return items


@bp.route("/")
def media_view():
    return render_template("media.html", media_items=_all_media())


@bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Keine Datei"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Kein Dateiname"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Format nicht erlaubt: {ext}"}), 400

    # File size check (read stream without saving)
    MAX_BYTES = 200 * 1024 * 1024  # 200 MB
    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_BYTES:
        return jsonify({"error": f"Datei zu groß ({size // (1024*1024)} MB). Maximum: 200 MB"}), 400

    media_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    save_path = MEDIA_DIR / media_id
    file.save(str(save_path))

    sidecar = {
        "media_id":          media_id,
        "original_filename": secure_filename(file.filename),
        "uploaded_at":       datetime.now().isoformat(),
        "status":            "uploaded",
        "ai_analysis":       None,
        "queue_status":      "pending",
    }
    save_path.with_suffix(".json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return jsonify({"ok": True, "media_id": media_id, "filename": media_id})


@bp.route("/analyze/<media_id>", methods=["POST"])
def analyze(media_id):
    source = MEDIA_DIR / media_id
    if not source.exists():
        return jsonify({"error": "Datei nicht gefunden"}), 404

    platform = request.get_json(silent=True) or {}
    platform = platform.get("platform", "instagram")

    from bot.config import load_config
    from dashboard.services.media_processor import MediaProcessor

    def _run():
        config = load_config()
        MediaProcessor(config).process(media_id, platform=platform)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "status": "Analyse gestartet"})


@bp.route("/file/<path:filename>")
def serve_file(filename):
    return send_from_directory(str(MEDIA_DIR.resolve()), filename)


@bp.route("/processed/<path:filename>")
def serve_processed(filename):
    return send_from_directory(str(PROCESSED_DIR.resolve()), filename)


@bp.route("/status/<media_id>")
def analyze_status(media_id):
    """Polling endpoint — gibt aktuellen Analysestatus zurück."""
    sidecar = (MEDIA_DIR / media_id).with_suffix(".json")
    if not sidecar.exists():
        return jsonify({"status": "unknown"})
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        return jsonify({
            "status":      meta.get("status", "unknown"),
            "error":       meta.get("error", ""),
            "ai_analysis": meta.get("ai_analysis"),
        })
    except Exception:
        return jsonify({"status": "unknown"})
