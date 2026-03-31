from flask import Blueprint, render_template, jsonify
from bot.analytics import Analytics
from bot.config import load_config
from datetime import datetime, timedelta
import json
from pathlib import Path

bp = Blueprint("overview", __name__)
CALENDAR_FILE  = Path("client/content_calendar.json")
LOG_FILE       = Path("bot.log")
CONV_FILE      = Path("client/conversations.json")
SUBMISSIONS_DIR = Path("client/submissions")
BRAND_FILE      = Path("client/brand_knowledge.json")


def _read_log_tail(n=30):
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


def _bot_status():
    """Prüft ob der Bot aktiv läuft (log in letzten 5 Min geschrieben)."""
    if not LOG_FILE.exists():
        return "unbekannt"
    import time
    age_sec = time.time() - LOG_FILE.stat().st_mtime
    if age_sec < 300:
        return "läuft"
    elif age_sec < 3600:
        return "inaktiv"
    return "gestoppt"


def _calendar_stats():
    if not CALENDAR_FILE.exists():
        return {"today": 0, "week": 0, "pending": 0, "next_post": None}
    try:
        data  = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        posts = data.get("posts", [])
        today = datetime.now().date().isoformat()
        now   = datetime.now()
        week_end = now + timedelta(days=7)
        today_count = sum(1 for p in posts if p.get("scheduled_time","").startswith(today))
        week_count  = 0
        pending     = 0
        next_post   = None
        for p in sorted(posts, key=lambda x: x.get("scheduled_time","")):
            try:
                t = datetime.fromisoformat(p["scheduled_time"])
                if t >= now and t <= week_end:
                    week_count += 1
                if t >= now and next_post is None:
                    next_post = {"time": t.strftime("%d.%m. %H:%M"), "platform": p.get("platform",""), "topic": p.get("topic","")[:40]}
            except Exception:
                pass
            if p.get("approval_status") == "pending" and p.get("status") not in ("gepostet","fehler"):
                pending += 1
        return {"today": today_count, "week": week_count, "pending": pending, "next_post": next_post}
    except Exception:
        return {"today": 0, "week": 0, "pending": 0, "next_post": None}


def _pending_submissions() -> list:
    if not SUBMISSIONS_DIR.exists():
        return []
    active_submission = ""
    if BRAND_FILE.exists():
        try:
            bk = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
            active_submission = bk.get("source_submission", "")
        except Exception:
            pass
    items = []
    for f in sorted(SUBMISSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            items.append({
                "filename": f.name,
                "company":   d.get("company_name", "Unbekannt"),
                "contact":   d.get("contact_name", ""),
                "submitted": d.get("_submitted_at", "")[:16].replace("T", " "),
                "imported":  f.name == active_submission,
            })
        except Exception:
            pass
    return items


@bp.route("/")
def overview():
    config = load_config()
    analytics = Analytics()

    platform_list = ["instagram", "facebook", "linkedin", "twitter", "tiktok"]
    summaries = {}
    for p in platform_list:
        summaries[p] = analytics.get_platform_summary(p, days=7)

    tokens = {
        "instagram": config["instagram"]["access_token"],
        "facebook":  config["facebook"]["access_token"],
        "linkedin":  config["linkedin"]["access_token"],
        "twitter":   config["twitter"]["api_key"],
        "tiktok":    config["tiktok"]["access_token"],
    }
    platform_status = {
        p: bool(t and "dein" not in t)
        for p, t in tokens.items()
    }

    log_lines = _read_log_tail(30)
    cal_stats = _calendar_stats()

    # Unresolved escalations from DM handler
    escalations = []
    if CONV_FILE.exists():
        try:
            convs = json.loads(CONV_FILE.read_text(encoding="utf-8"))
            escalations = [c for c in convs if c.get("escalate")]
        except Exception:
            pass

    # Brand konfiguriert?
    brand_configured = False
    if BRAND_FILE.exists():
        try:
            bk = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
            brand_configured = bool(bk.get("brand_name") or bk.get("confirmed_by_user"))
        except Exception:
            pass

    return render_template(
        "overview.html",
        summaries=summaries,
        platform_status=platform_status,
        log_lines=log_lines,
        cal_stats=cal_stats,
        escalations=escalations,
        bot_status=_bot_status(),
        now=datetime.now(),
        brand_configured=brand_configured,
    )


@bp.route("/api/log")
def log_tail():
    return jsonify({"lines": _read_log_tail(30)})


@bp.route("/verlauf/")
@bp.route("/verlauf")
def history():
    if not CALENDAR_FILE.exists():
        return render_template("verlauf.html", posts=[], total=0)
    try:
        data   = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        posted = [p for p in data.get("posts", []) if p.get("status") in ("gepostet", "fehler", "abgelehnt", "freigegeben")]
        posted.sort(key=lambda x: x.get("scheduled_time", ""), reverse=True)
    except Exception:
        posted = []
    return render_template("verlauf.html", posts=posted, total=len(posted))
