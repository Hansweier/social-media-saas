"""
Kunden-Vorschau-Seite — öffentlich zugänglich (kein Login nötig).
Kunde sieht geplante Posts und kann einzelne freigeben oder ablehnen.
URL: /vorschau
"""
from flask import Blueprint, render_template, request, jsonify
from bot.content_calendar import ContentCalendar
from datetime import datetime
import json
from pathlib import Path

bp = Blueprint("preview", __name__, url_prefix="/kunden-vorschau")
QUEUE_DIR = Path("client/media/queue")


@bp.route("/")
def client_preview():
    cal   = ContentCalendar()
    posts = cal.get_upcoming_posts(days=14)

    # Media-Queue auch anzeigen
    media_queue = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("queue_status") in ("ready", "approved"):
                media_queue.append(m)
        except Exception:
            pass

    return render_template(
        "preview.html",
        posts=posts,
        media_queue=media_queue,
        now=datetime.now(),
    )


@bp.route("/approve/<post_id>", methods=["POST"])
def approve_post(post_id):
    cal = ContentCalendar()
    ok  = cal.update_post(post_id, status="freigegeben",
                          approval_status="freigegeben",
                          approved_at=datetime.now().isoformat())
    return jsonify({"ok": ok})


@bp.route("/reject/<post_id>", methods=["POST"])
def reject_post(post_id):
    cal = ContentCalendar()
    ok  = cal.update_post(post_id, status="abgelehnt", approval_status="abgelehnt")
    return jsonify({"ok": ok})


@bp.route("/approve-media/<media_id>", methods=["POST"])
def approve_media(media_id):
    path = QUEUE_DIR / f"{media_id}.json"
    if not path.exists():
        return jsonify({"error": "nicht gefunden"}), 404
    m = json.loads(path.read_text(encoding="utf-8"))
    m["queue_status"] = "approved"
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True})
