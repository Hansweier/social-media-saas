"""
Kunden-Onboarding — Fragebogen.
Einfache Einrichtung einer neuen Marke in 4 Schritten.
Speichert brand_knowledge.json und passt bot_settings.json an.
"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import json
from datetime import datetime

bp = Blueprint("fragebogen", __name__, url_prefix="/fragebogen")

BRAND_FILE    = Path("client/brand_knowledge.json")
SETTINGS_FILE = Path("client/bot_settings.json")

ALL_PLATFORMS = {"instagram", "facebook", "linkedin", "twitter", "tiktok"}


@bp.route("/", strict_slashes=False)
@bp.route("")
def show():
    return render_template("fragebogen.html")


@bp.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}

    brand_name   = data.get("brand_name", "").strip()
    industry     = data.get("industry", "").strip()
    mission      = data.get("mission", "").strip()
    slogan       = data.get("slogan", "").strip()
    target_aud   = data.get("target_audience", "").strip()
    tone_kws     = [t.strip() for t in data.get("tone_keywords", []) if t.strip()]
    pillars      = [p.strip() for p in data.get("content_pillars", []) if p.strip()]
    platforms    = [p for p in data.get("platforms", []) if p in ALL_PLATFORMS]

    if not brand_name:
        return jsonify({"ok": False, "error": "Firmenname fehlt"}), 400

    # ── brand_knowledge.json speichern ────────────────────────────────────────
    BRAND_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if BRAND_FILE.exists():
        try:
            existing = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    brand_data = {
        **existing,
        "brand_name":      brand_name,
        "industry":        industry,
        "mission":         mission,
        "slogan":          slogan,
        "target_audience": target_aud,
        "tone_keywords":   tone_kws,
        "content_pillars": pillars,
        "active_platforms": platforms,
        "confirmed_by_user": True,
        "onboarded_at":    datetime.now().isoformat(),
    }
    BRAND_FILE.write_text(
        json.dumps(brand_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── bot_settings.json: nur aktive Plattformen in Schedule aktivieren ──────
    if platforms:
        try:
            settings = {}
            if SETTINGS_FILE.exists():
                settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

            # Inaktive Plattformen pausieren
            paused = set(settings.get("paused_platforms", []))
            for p in ALL_PLATFORMS:
                if p not in platforms:
                    paused.add(p)
                else:
                    paused.discard(p)
            settings["paused_platforms"] = sorted(paused)

            SETTINGS_FILE.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # non-fatal

    return jsonify({"ok": True, "brand_name": brand_name})
