from flask import Blueprint, jsonify, request
from bot.config import load_config
from bot.analytics import Analytics
import json
from pathlib import Path
from datetime import datetime

bp = Blueprint("api", __name__, url_prefix="/api")
QUEUE_DIR = Path("client/media/queue")


@bp.route("/status")
def status():
    config = load_config()
    checks = {
        "instagram": config["instagram"]["access_token"],
        "facebook":  config["facebook"]["access_token"],
        "linkedin":  config["linkedin"]["access_token"],
        "twitter":   config["twitter"]["api_key"],
        "tiktok":    config["tiktok"]["access_token"],
    }
    platforms = {
        p: bool(t and "dein" not in t)
        for p, t in checks.items()
    }
    return jsonify({
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "claude_configured": bool(config["claude"]["api_key"]),
        "platforms": platforms,
    })


@bp.route("/queue")
def queue():
    items = []
    if not QUEUE_DIR.exists():
        return jsonify(items)
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify(items)


@bp.route("/queue/<media_id>/approve", methods=["POST"])
def approve(media_id):
    manifest_path = QUEUE_DIR / f"{media_id}.json"
    if not manifest_path.exists():
        return jsonify({"error": "nicht gefunden"}), 404
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["queue_status"] = "approved"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True})


@bp.route("/queue/<media_id>", methods=["DELETE"])
def remove_from_queue(media_id):
    manifest_path = QUEUE_DIR / f"{media_id}.json"
    if manifest_path.exists():
        manifest_path.unlink()
    return jsonify({"ok": True})


# ── Notifications ─────────────────────────────────────────────────────────────

@bp.route("/notifications")
def get_notifications():
    from dashboard.services.notification_service import get_unread
    return jsonify(get_unread())


@bp.route("/notifications/<nid>/read", methods=["POST"])
def read_notification(nid):
    from dashboard.services.notification_service import mark_read
    mark_read(nid)
    return jsonify({"ok": True})


@bp.route("/notifications/read-all", methods=["POST"])
def read_all_notifications():
    from dashboard.services.notification_service import mark_all_read
    mark_all_read()
    return jsonify({"ok": True})


# ── Generation Config ─────────────────────────────────────────────────────────

@bp.route("/generation-config", methods=["GET", "POST"])
def generation_config():
    from dashboard.services.variant_service import get_generation_config, set_generation_config
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        mode  = data.get("mode", "weekly")
        hours = int(data.get("hours_before", 4))
        set_generation_config(mode, hours)
        return jsonify({"ok": True, "mode": mode, "hours_before": hours})
    return jsonify(get_generation_config())


# ── Research Agent (Claude Agent SDK) ─────────────────────────────────────────

_research_running = False


@bp.route("/research-trends", methods=["POST"])
def start_research():
    """Startet Agent SDK Trend-Recherche im Hintergrund."""
    global _research_running
    if _research_running:
        return jsonify({"ok": False, "error": "Recherche läuft bereits"}), 409

    import threading

    def _run():
        global _research_running
        try:
            from dashboard.services.research_agent import run_research_sync
            run_research_sync()
        finally:
            _research_running = False

    _research_running = True
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "Recherche gestartet..."})


@bp.route("/research-trends", methods=["GET"])
def get_research():
    """Gibt zuletzt gespeicherte Recherche-Ergebnisse zurück."""
    from dashboard.services.research_agent import load_latest_research
    data = load_latest_research()
    return jsonify({**data, "running": _research_running})


@bp.route("/research-apply", methods=["POST"])
def apply_research():
    """Übernimmt vorgeschlagene Topics als neue Content-Säulen."""
    data   = request.get_json(silent=True) or {}
    topics = data.get("topics", [])
    if not topics or not isinstance(topics, list):
        return jsonify({"error": "Keine Topics übergeben"}), 400
    bk_file = Path("client/brand_knowledge.json")
    try:
        bk = json.loads(bk_file.read_text(encoding="utf-8")) if bk_file.exists() else {}
        bk["content_pillars"]    = [str(t) for t in topics[:10]]
        bk["pillars_updated_at"] = datetime.now().isoformat()
        bk_file.write_text(json.dumps(bk, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
