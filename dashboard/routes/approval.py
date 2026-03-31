"""
Approval Routes — Wöchentliche Content-Freigabe.
Ersetzt und erweitert preview.py.
"""
from flask import Blueprint, render_template, request, jsonify
from bot.content_calendar import ContentCalendar
from bot.config import load_config
from dashboard.services.variant_service import VariantService, get_mode, set_mode
from datetime import datetime, date, timedelta
import json, threading
from pathlib import Path

bp = Blueprint("approval", __name__, url_prefix="/vorschau")
QUEUE_DIR    = Path("client/media/queue")
_gen_status  = {"running": False, "done": 0, "total": 0, "error": ""}
_gen_lock    = threading.Lock()
_improve_jobs: dict = {}   # variant_id -> {done, content, error, ts}
_improve_lock = threading.Lock()
_IMPROVE_TTL  = 300        # Jobs nach 5 Minuten löschen


def _cleanup_improve_jobs():
    """Alte abgeschlossene Jobs entfernen (verhindert Memory-Leak)."""
    import time
    now = time.time()
    with _improve_lock:
        stale = [vid for vid, j in _improve_jobs.items()
                 if j.get("done") and now - j.get("ts", 0) > _IMPROVE_TTL]
        for vid in stale:
            _improve_jobs.pop(vid, None)


def _get_week_start(offset_weeks=0) -> date:
    today    = datetime.now().date()
    monday   = today - timedelta(days=today.weekday())
    return monday + timedelta(weeks=offset_weeks)


def _week_label(week_start: date) -> str:
    end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%d.%m.')} – {end.strftime('%d.%m.%Y')}"


def _media_queue() -> list:
    items = []
    for f in sorted(QUEUE_DIR.glob("*.json")):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("queue_status") in ("ready", "approved"):
                items.append(m)
        except Exception:
            pass
    return items


# ─── Hauptseite: Wochenansicht ────────────────────────────────────────────────

@bp.route("/")
@bp.route("/woche")
def week_view():
    offset     = int(request.args.get("w", 0))
    week_start = _get_week_start(offset)
    cal        = ContentCalendar()
    by_day     = cal.get_week_posts(week_start)
    mode       = get_mode()

    # Stats
    total, freigegeben, pending = 0, 0, 0
    for posts in by_day.values():
        for p in posts:
            total += 1
            st = p.get("approval_status", "pending")
            if st == "freigegeben": freigegeben += 1
            elif st == "pending":   pending += 1

    confident_ids = [
        p["id"]
        for posts in by_day.values()
        for p in posts
        if p.get("approval_status") == "pending"
        and p.get("variants")
        and max((v["ai_score"] for v in p["variants"]), default=0) >= 0.8
    ]

    day_names  = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
    week_days  = [week_start + timedelta(days=i) for i in range(7)]

    return render_template(
        "woche.html",
        mode=mode,
        by_day=by_day,
        week_days=week_days,
        day_names=day_names,
        week_label=_week_label(week_start),
        offset=offset,
        total=total,
        freigegeben=freigegeben,
        pending=pending,
        confident_ids=confident_ids,
        media_queue=_media_queue(),
        now=datetime.now(),
    )


# ─── Woche generieren ────────────────────────────────────────────────────────

@bp.route("/woche-generieren", methods=["POST"])
def generate_week():
    from dashboard.services.plan_service import can_generate
    allowed, reason = can_generate()
    if not allowed:
        return jsonify({"ok": False, "error": reason, "upgrade": True})

    with _gen_lock:
        if _gen_status["running"]:
            return jsonify({"ok": False, "error": "Läuft bereits"})
        _gen_status.update({"running": True, "done": 0, "total": 0, "error": ""})

    def _run():
        try:
            from dashboard.services.plan_service import can_generate, track_post_generated
            config = load_config()
            svc    = VariantService(config["claude"]["api_key"])
            cal    = ContentCalendar()
            plan   = cal.generate_weekly_plan()
            _gen_status["total"] = len(plan)
            for entry in plan:
                ok, reason = can_generate()
                if not ok:
                    _gen_status["error"] = reason
                    break
                try:
                    variants = svc.generate_variants(entry["platform"], entry["topic"])
                    cal.update_post(entry["id"],
                        variants=variants,
                        content=next((v["content"] for v in variants if v["selected"]), None),
                        selected_variant_id=next((v["variant_id"] for v in variants if v["selected"]), None),
                    )
                    track_post_generated()
                except Exception as e:
                    _gen_status["error"] = str(e)
                _gen_status["done"] += 1
        except Exception as e:
            _gen_status["error"] = str(e)
        finally:
            _gen_status["running"] = False

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/woche-generieren/status")
def generate_week_status():
    return jsonify(_gen_status)


@bp.route("/woche-generieren/abbrechen", methods=["POST"])
def cancel_week_generation():
    _gen_status["running"] = False
    _gen_status["error"]   = "Durch Nutzer abgebrochen"
    return jsonify({"ok": True})


# ─── Modus wechseln ──────────────────────────────────────────────────────────

@bp.route("/modus", methods=["GET", "POST"])
def mode_endpoint():
    if request.method == "POST":
        new_mode = request.get_json(silent=True) or {}
        new_mode = new_mode.get("mode", "copilot")
        set_mode(new_mode)
        return jsonify({"ok": True, "mode": new_mode})
    return jsonify({"mode": get_mode()})


# ─── Varianten generieren ────────────────────────────────────────────────────

@bp.route("/varianten/<post_id>", methods=["POST"])
def generate_variants(post_id):
    from dashboard.services.plan_service import can_generate
    allowed, reason = can_generate()
    if not allowed:
        return jsonify({"error": reason, "upgrade": True}), 402

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "Post nicht gefunden"}), 404

    post = posts[0]

    # Clear variants so polling waits for fresh generation
    cal.update_post(post_id, variants=[], approval_status="pending")

    def _gen():
        from dashboard.services.plan_service import track_post_generated
        config   = load_config()
        svc      = VariantService(config["claude"]["api_key"])
        variants = svc.generate_variants(post["platform"], post.get("topic", ""))
        cal.update_post(post_id, variants=variants,
                        selected_variant_id=next((v["variant_id"] for v in variants if v["selected"]), None),
                        content=next((v["content"] for v in variants if v["selected"]), post.get("content")))
        track_post_generated()

    threading.Thread(target=_gen, daemon=True).start()
    return jsonify({"ok": True, "status": "generiert"})


# ─── Varianten-Status (Polling nach Regen) ───────────────────────────────────

@bp.route("/varianten-status/<post_id>")
def variant_status(post_id):
    """Polling: hat der Post jetzt Varianten? Gibt variants zurück wenn fertig."""
    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"ready": False})
    post = posts[0]
    variants = post.get("variants") or []
    if variants:
        return jsonify({"ready": True, "variants": variants,
                        "selected_variant_id": post.get("selected_variant_id"),
                        "content": post.get("content", ""),
                        "approval_status": post.get("approval_status", "pending")})
    return jsonify({"ready": False})


# ─── Variante auswählen ───────────────────────────────────────────────────────

@bp.route("/variant/waehlen", methods=["POST"])
def select_variant():
    data          = request.get_json()
    post_id       = data.get("post_id")
    variant_id    = data.get("variant_id")
    approval_note = data.get("approval_note", "").strip()

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "Post nicht gefunden"}), 404

    post = VariantService.select_variant_static(posts[0], variant_id)
    if not post:
        return jsonify({"error": "Variante nicht gefunden"}), 404
    cal.update_post(post_id,
                    content=post["content"],
                    selected_variant_id=post["selected_variant_id"],
                    approval_status="freigegeben",
                    approved_at=post["approved_at"],
                    status="freigegeben",
                    variants=post["variants"])
    # Learning: Freigabe mit Content merken
    try:
        from dashboard.services.learning_service import record_approval
        selected_v = next((v for v in post.get("variants", []) if v["variant_id"] == variant_id), {})
        record_approval(
            post_id, posts[0].get("platform", ""), posts[0].get("topic", ""),
            selected_v.get("type", "A"), selected_v.get("ai_score", 0.0),
            content=selected_v.get("content", ""),
            note=approval_note,
        )
    except Exception:
        pass
    return jsonify({"ok": True})


# ─── Freigabe: bester Vorschlag bestätigen ────────────────────────────────────

@bp.route("/freigeben/<post_id>", methods=["POST"])
def approve_post(post_id):
    data          = request.get_json(silent=True) or {}
    approval_note = data.get("approval_note", "").strip()

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "nicht gefunden"}), 404
    post = posts[0]
    # Wähle automatisch die vorausgewählte Variante
    selected = next((v for v in post.get("variants", []) if v.get("selected")), None)
    vid = selected["variant_id"] if selected else None

    cal.update_post(post_id,
                    approval_status="freigegeben",
                    approved_at=datetime.now().isoformat(),
                    status="freigegeben",
                    content=selected["content"] if selected else post.get("content"),
                    selected_variant_id=vid)
    try:
        from dashboard.services.learning_service import record_approval
        record_approval(
            post_id, post.get("platform", ""), post.get("topic", ""),
            selected.get("type", "A") if selected else "A",
            selected.get("ai_score", 0.0) if selected else 0.0,
            content=selected.get("content", "") if selected else post.get("content", ""),
            note=approval_note,
        )
    except Exception:
        pass
    return jsonify({"ok": True})


# ─── Alle confident Posts auf einmal freigeben ───────────────────────────────

@bp.route("/freigeben-alle", methods=["POST"])
def approve_all_confident():
    data = request.get_json(silent=True) or {}
    ids  = data.get("ids", [])
    cal  = ContentCalendar()
    count = 0
    for post_id in ids:
        posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
        if not posts:
            continue
        post     = posts[0]
        selected = next((v for v in post.get("variants", []) if v.get("selected")), None)
        cal.update_post(post_id,
                        approval_status="freigegeben",
                        approved_at=datetime.now().isoformat(),
                        status="freigegeben",
                        content=selected["content"] if selected else post.get("content"),
                        selected_variant_id=selected["variant_id"] if selected else None)
        count += 1
    return jsonify({"ok": True, "approved": count})


# ─── Variante bearbeiten (inline edit) ───────────────────────────────────────

@bp.route("/variant/bearbeiten", methods=["POST"])
def edit_variant():
    data       = request.get_json(silent=True) or {}
    post_id    = data.get("post_id")
    variant_id = data.get("variant_id")
    content    = data.get("content", "").strip()
    if not post_id or not variant_id or not content:
        return jsonify({"error": "Fehlende Parameter"}), 400

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "Post nicht gefunden"}), 404

    post = posts[0]
    for v in post.get("variants", []):
        if v["variant_id"] == variant_id:
            v["content"] = content
            v["edited"]  = True
            break
    # Also update main content if this variant is selected
    if post.get("selected_variant_id") == variant_id:
        post["content"] = content
    cal.update_post(post_id, variants=post["variants"], content=post.get("content"))
    return jsonify({"ok": True})


# ─── Ablehnen ────────────────────────────────────────────────────────────────

@bp.route("/ablehnen/<post_id>", methods=["POST"])
def reject_post(post_id):
    data            = request.get_json(silent=True) or {}
    reason_category = data.get("reason_category", "sonstige")
    reason_text     = data.get("reason_text", "").strip()

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    post  = posts[0] if posts else {}

    cal.update_post(post_id, approval_status="abgelehnt", status="abgelehnt")

    try:
        from dashboard.services.learning_service import record_rejection
        selected_v = next((v for v in post.get("variants", []) if v.get("selected")), {})
        record_rejection(post_id, post.get("platform", ""), post.get("topic", ""),
                         selected_v.get("type", "A"), reason_category, reason_text)
    except Exception:
        pass
    return jsonify({"ok": True})


@bp.route("/ablehnen-rueckgaengig/<post_id>", methods=["POST"])
def undo_reject(post_id):
    cal = ContentCalendar()
    cal.update_post(post_id, approval_status="pending", status="geplant")
    return jsonify({"ok": True})


# ─── Regenerieren ────────────────────────────────────────────────────────────

@bp.route("/regenerieren/<post_id>", methods=["POST"])
def regenerate(post_id):
    data  = request.get_json(silent=True) or {}
    rtype = data.get("type", "angle")  # "angle" | "topic"

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "Post nicht gefunden"}), 404
    post = posts[0]

    # Clear variants NOW so the status endpoint returns {ready: False} until new ones arrive
    cal.update_post(post_id, variants=[], approval_status="pending")

    def _regen():
        from dashboard.services.plan_service import can_generate, track_post_generated
        ok, reason = can_generate()
        if not ok:
            cal.update_post(post_id, approval_status="pending")
            return
        config   = load_config()
        svc      = VariantService(config["claude"]["api_key"])
        topic    = post.get("topic", "")

        # Bei "topic": neues Topic aus Rotation holen
        if rtype == "topic":
            from bot.content_calendar import ContentCalendar as CC
            cal2 = CC()
            rotation = cal2.topic_rotation.get(post["platform"], [])
            import random
            if rotation:
                topic = random.choice([t for t in rotation if t != topic] or rotation)

        variants = svc.generate_variants(post["platform"], topic)
        cal.update_post(post_id,
                        variants=variants,
                        content=next((v["content"] for v in variants if v["selected"]), None),
                        selected_variant_id=next((v["variant_id"] for v in variants if v["selected"]), None),
                        approval_status="pending")
        track_post_generated()

    threading.Thread(target=_regen, daemon=True).start()
    return jsonify({"ok": True, "status": "regeneriert"})


# ─── Media freigeben ─────────────────────────────────────────────────────────

@bp.route("/approve-media/<media_id>", methods=["POST"])
def approve_media(media_id):
    path = QUEUE_DIR / f"{media_id}.json"
    if not path.exists():
        return jsonify({"error": "nicht gefunden"}), 404
    m = json.loads(path.read_text(encoding="utf-8"))
    m["queue_status"] = "approved"
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True})


# ─── KI-Verbesserung einer einzelnen Variante ────────────────────────────────

@bp.route("/variant/verbessern", methods=["POST"])
def improve_variant():
    data        = request.get_json(silent=True) or {}
    post_id     = data.get("post_id")
    variant_id  = data.get("variant_id")
    instruction = data.get("instruction", "Verbessere den Post").strip()

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"error": "Post nicht gefunden"}), 404
    post = posts[0]
    variant = next((v for v in post.get("variants", []) if v["variant_id"] == variant_id), None)
    if not variant:
        return jsonify({"error": "Variante nicht gefunden"}), 404

    import time
    _cleanup_improve_jobs()
    with _improve_lock:
        _improve_jobs[variant_id] = {"done": False, "content": "", "error": "", "ts": time.time()}

    def _run():
        try:
            config   = load_config()
            svc      = VariantService(config["claude"]["api_key"])
            improved = svc.improve_variant(post["platform"], variant["content"], instruction)
            # Update variant in calendar
            cal2 = ContentCalendar()
            p2   = next((p for p in cal2.calendar["posts"] if p["id"] == post_id), None)
            if p2:
                for v in p2.get("variants", []):
                    if v["variant_id"] == variant_id:
                        v["content"] = improved
                        v["edited"]  = True
                        break
                if p2.get("selected_variant_id") == variant_id:
                    p2["content"] = improved
                cal2.update_post(post_id, variants=p2["variants"], content=p2.get("content"))
            import time as _t
            with _improve_lock:
                _improve_jobs[variant_id] = {"done": True, "content": improved, "error": "", "ts": _t.time()}
        except Exception as e:
            import time as _t
            with _improve_lock:
                _improve_jobs[variant_id] = {"done": True, "content": "", "error": str(e), "ts": _t.time()}

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


@bp.route("/variant/verbessern-status/<variant_id>")
def improve_variant_status(variant_id):
    with _improve_lock:
        job = _improve_jobs.get(variant_id)
    if not job:
        return jsonify({"done": False})
    if job["done"] and not job["error"]:
        # Clean up after delivering result
        with _improve_lock:
            _improve_jobs.pop(variant_id, None)
    return jsonify(job)


# ─── Variante bewerten (Reaction) ─────────────────────────────────────────────

@bp.route("/variant/bewerten", methods=["POST"])
def rate_variant():
    data       = request.get_json(silent=True) or {}
    post_id    = data.get("post_id")
    variant_id = data.get("variant_id")
    rating     = data.get("rating", "")  # "love" | "good" | "meh"

    cal   = ContentCalendar()
    posts = [p for p in cal.calendar["posts"] if p["id"] == post_id]
    if not posts:
        return jsonify({"ok": True})  # soft fail — no disruption

    post = posts[0]
    variant = next((v for v in post.get("variants", []) if v["variant_id"] == variant_id), None)
    if not variant:
        return jsonify({"ok": True})

    try:
        from dashboard.services.learning_service import record_rating
        record_rating(
            post_id, post.get("platform", ""), post.get("topic", ""),
            variant.get("type", "A"), rating, variant.get("content", ""),
        )
    except Exception:
        pass
    return jsonify({"ok": True})
