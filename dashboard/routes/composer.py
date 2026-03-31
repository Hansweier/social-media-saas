from flask import Blueprint, render_template, request, jsonify
from bot.poster import Poster
from bot.config import load_config
import threading, uuid, time
import json
from pathlib import Path

bp = Blueprint("composer", __name__, url_prefix="/composer")
QUEUE_DIR  = Path("client/media/queue")
PLATFORMS  = ["instagram", "facebook", "linkedin", "twitter", "tiktok"]
_post_jobs: dict = {}   # job_id -> {status, platform, message}
_jobs_lock = threading.Lock()


def _ready_media():
    items = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("queue_status") in ("ready", "approved"):
                items.append(m)
        except Exception:
            pass
    return items


@bp.route("/")
def composer_view():
    return render_template("composer.html", platforms=PLATFORMS, media_queue=_ready_media())


@bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json()
    platform = data.get("platform", "instagram")
    from brand.foerderkraft_brand import get_brand as _gb
    topic    = data.get("topic") or _gb().get("name", "Social Media Post")
    try:
        config  = load_config()
        poster  = Poster(config)
        content = poster.generate_content(platform, topic)
        return jsonify({"content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/post", methods=["POST"])
def post_now():
    data     = request.get_json()
    platform = data.get("platform")
    topic    = data.get("topic", "")
    content  = data.get("content", "")
    media_id = data.get("media_id")

    image_url = None
    if media_id:
        processed = Path("client/media/processed") / media_id
        if processed.exists():
            image_url = f"/media/processed/{media_id}"

    job_id = str(uuid.uuid4())[:8]
    with _jobs_lock:
        _post_jobs[job_id] = {"status": "running", "platform": platform, "message": "Verbinde..."}

    def _post():
        try:
            config = load_config()
            poster = Poster(config)
            result = poster.post(platform, content, topic, image_url=image_url)
            if result.get("success"):
                # Track in calendar so it appears in /verlauf/
                from bot.content_calendar import ContentCalendar
                from bot.analytics import Analytics
                from datetime import datetime
                cal = ContentCalendar()
                post_id = cal.add_post(platform, topic, datetime.now(),
                                       content=content, status="gepostet")
                cal.update_post(post_id, approval_status="freigegeben",
                                post_id=result.get("post_id"))
                Analytics().track_post(platform, result.get("post_id", ""), topic)
                _post_jobs[job_id] = {"status": "success", "platform": platform,
                                      "message": result.get("message", "Erfolgreich gepostet!")}
            else:
                _post_jobs[job_id] = {"status": "error", "platform": platform,
                                      "message": result.get("error", "Unbekannter Fehler")}
        except Exception as e:
            with _jobs_lock:
                _post_jobs[job_id] = {"status": "error", "platform": platform, "message": str(e)}
        # Cleanup old jobs (keep last 50)
        with _jobs_lock:
            if len(_post_jobs) > 50:
                oldest = next(iter(_post_jobs))
                _post_jobs.pop(oldest, None)

    threading.Thread(target=_post, daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id})


@bp.route("/post-status/<job_id>")
def post_status(job_id):
    job = _post_jobs.get(job_id, {"status": "unknown", "message": "Job nicht gefunden"})
    return jsonify(job)
