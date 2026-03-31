"""
Learning Route — Zeigt und verwaltet das KI-Lernprofil.
"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import json

bp = Blueprint("learning", __name__, url_prefix="/lernen")
LEARNING_FILE = Path("client/learning_profile.json")


@bp.route("/")
def learning_page():
    from dashboard.services.learning_service import get_profile_summary, _load
    summary = get_profile_summary()
    profile = _load()
    return render_template("lernen.html", summary=summary, profile=profile)


@bp.route("/reset", methods=["POST"])
def reset_profile():
    data     = request.get_json(silent=True) or {}
    platform = data.get("platform", "all").lower()
    from dashboard.services.learning_service import _load, _save, _empty_platform, PLATFORMS
    profile = _load()
    if platform == "all":
        for p in PLATFORMS:
            profile["per_platform"][p] = _empty_platform()
        profile["global"] = {"always_avoid": [], "always_prefer": []}
    elif platform in PLATFORMS:
        profile["per_platform"][platform] = _empty_platform()
    _save(profile)
    return jsonify({"ok": True})


@bp.route("/global", methods=["POST"])
def update_global():
    """Fügt Einträge zu 'always_avoid' oder 'always_prefer' hinzu."""
    data   = request.get_json(silent=True) or {}
    key    = data.get("key", "")   # "always_avoid" | "always_prefer"
    action = data.get("action", "add")  # "add" | "remove"
    value  = data.get("value", "").strip()

    if key not in ("always_avoid", "always_prefer") or not value:
        return jsonify({"error": "Ungültige Parameter"}), 400

    from dashboard.services.learning_service import _load, _save
    profile = _load()
    lst = profile["global"].setdefault(key, [])
    if action == "add" and value not in lst:
        lst.append(value)
    elif action == "remove" and value in lst:
        lst.remove(value)
    _save(profile)
    return jsonify({"ok": True, "list": lst})


@bp.route("/topic", methods=["POST"])
def update_topic():
    """Entfernt ein Thema manuell aus rejected/approved lists."""
    data     = request.get_json(silent=True) or {}
    platform = data.get("platform", "")
    list_key = data.get("list", "")    # "approved_topics" | "rejected_topics"
    action   = data.get("action", "remove")
    value    = data.get("value", "").strip()

    from dashboard.services.learning_service import _load, _save, PLATFORMS
    if platform not in PLATFORMS or list_key not in ("approved_topics", "rejected_topics"):
        return jsonify({"error": "Ungültige Parameter"}), 400

    profile = _load()
    lst = profile["per_platform"].get(platform, {}).get(list_key, [])
    if action == "remove" and value in lst:
        lst.remove(value)
        profile["per_platform"][platform][list_key] = lst
        _save(profile)
    return jsonify({"ok": True})
