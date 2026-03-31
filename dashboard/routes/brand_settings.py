from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from dashboard.services.brand_extractor import BrandExtractor
from bot.config import load_config
from pathlib import Path
from datetime import datetime
import json
import re
import logging

log = logging.getLogger(__name__)

bp = Blueprint("brand_settings", __name__, url_prefix="/einstellungen")
PDF_UPLOAD_DIR = Path("client/brand_pdfs")
PDF_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = Path(".env")

# ── .env Helpers ─────────────────────────────────────────────────────────────

def _write_env_key(key: str, value: str):
    """Update or append key=value in .env, preserving all comments and order."""
    content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    if re.search(pattern, content):
        new_content = re.sub(pattern, new_line, content)
    else:
        new_content = content.rstrip("\n") + "\n" + new_line + "\n"
    ENV_FILE.write_text(new_content, encoding="utf-8")

def _read_env_key(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""

# ── Token test helpers ────────────────────────────────────────────────────────

def _test_claude(api_key: str) -> dict:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=5,
                               messages=[{"role": "user", "content": "Hi"}])
        return {"ok": True, "msg": "Claude API erreichbar"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}

def _test_instagram(token: str, account_id: str) -> dict:
    try:
        import requests as rq
        r = rq.get("https://graph.facebook.com/v18.0/me",
                   params={"access_token": token, "fields": "id,name"}, timeout=8)
        if r.status_code == 200:
            name = r.json().get("name", "")
            return {"ok": True, "msg": f"Verbunden als: {name}"}
        return {"ok": False, "msg": r.json().get("error", {}).get("message", r.text[:100])}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}

def _test_facebook(token: str) -> dict:
    try:
        import requests as rq
        r = rq.get("https://graph.facebook.com/v18.0/me",
                   params={"access_token": token, "fields": "id,name"}, timeout=8)
        if r.status_code == 200:
            name = r.json().get("name", "")
            return {"ok": True, "msg": f"Verbunden als: {name}"}
        return {"ok": False, "msg": r.json().get("error", {}).get("message", r.text[:100])}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}

def _test_linkedin(token: str) -> dict:
    try:
        import requests as rq
        r = rq.get("https://api.linkedin.com/v2/me",
                   headers={"Authorization": f"Bearer {token}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            name = f"{d.get('localizedFirstName','')} {d.get('localizedLastName','')}".strip()
            return {"ok": True, "msg": f"Verbunden als: {name}"}
        return {"ok": False, "msg": r.json().get("message", r.text[:100])}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}

def _test_twitter(bearer_token: str) -> dict:
    try:
        import requests as rq
        r = rq.get("https://api.twitter.com/2/users/me",
                   headers={"Authorization": f"Bearer {bearer_token}"}, timeout=8)
        if r.status_code == 200:
            name = r.json().get("data", {}).get("name", "")
            return {"ok": True, "msg": f"Verbunden als: {name}"}
        return {"ok": False, "msg": r.json().get("detail", r.text[:100])}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def _build_token_status(config):
    return {
        "instagram": bool(config["instagram"]["access_token"] and "dein" not in config["instagram"]["access_token"]),
        "facebook":  bool(config["facebook"]["access_token"]  and "dein" not in config["facebook"]["access_token"]),
        "linkedin":  bool(config["linkedin"]["access_token"]  and "dein" not in config["linkedin"]["access_token"]),
        "twitter":   bool(config["twitter"]["api_key"]        and "dein" not in config["twitter"]["api_key"]),
        "tiktok":    bool(config["tiktok"]["access_token"]    and "dein" not in config["tiktok"]["access_token"]),
        "claude":    bool(config["claude"]["api_key"]         and "sk-ant" in config["claude"]["api_key"]),
    }


@bp.route("/marke")
def brand_page():
    facts  = BrandExtractor.load_brand_knowledge()
    config = load_config()
    token_status = _build_token_status(config)
    # Provide masked current values for input fields
    token_values = {
        "CLAUDE_API_KEY":                _read_env_key("CLAUDE_API_KEY"),
        "INSTAGRAM_ACCESS_TOKEN":        _read_env_key("INSTAGRAM_ACCESS_TOKEN"),
        "INSTAGRAM_ACCOUNT_ID":          _read_env_key("INSTAGRAM_ACCOUNT_ID"),
        "FACEBOOK_ACCESS_TOKEN":         _read_env_key("FACEBOOK_ACCESS_TOKEN"),
        "FACEBOOK_PAGE_ID":              _read_env_key("FACEBOOK_PAGE_ID"),
        "LINKEDIN_ACCESS_TOKEN":         _read_env_key("LINKEDIN_ACCESS_TOKEN"),
        "LINKEDIN_PERSON_ID":            _read_env_key("LINKEDIN_PERSON_ID"),
        "TWITTER_BEARER_TOKEN":          _read_env_key("TWITTER_BEARER_TOKEN"),
        "TWITTER_API_KEY":               _read_env_key("TWITTER_API_KEY"),
        "TWITTER_API_SECRET":            _read_env_key("TWITTER_API_SECRET"),
        "TWITTER_ACCESS_TOKEN":          _read_env_key("TWITTER_ACCESS_TOKEN"),
        "TWITTER_ACCESS_TOKEN_SECRET":   _read_env_key("TWITTER_ACCESS_TOKEN_SECRET"),
        "TIKTOK_ACCESS_TOKEN":           _read_env_key("TIKTOK_ACCESS_TOKEN"),
        "NOTIFY_EMAIL":                  _read_env_key("NOTIFY_EMAIL"),
        "SMTP_EMAIL":                    _read_env_key("SMTP_EMAIL"),
        "SMTP_PASSWORD":                 _read_env_key("SMTP_PASSWORD"),
    }
    from dashboard.services.variant_service import get_paused_platforms
    return render_template("marke.html", facts=facts, token_status=token_status,
                           token_values=token_values,
                           paused_platforms=get_paused_platforms())


@bp.route("/setup")
def setup_wizard():
    config = load_config()
    token_status = _build_token_status(config)
    token_values = {
        "CLAUDE_API_KEY":              _read_env_key("CLAUDE_API_KEY"),
        "INSTAGRAM_ACCESS_TOKEN":      _read_env_key("INSTAGRAM_ACCESS_TOKEN"),
        "INSTAGRAM_ACCOUNT_ID":        _read_env_key("INSTAGRAM_ACCOUNT_ID"),
        "FACEBOOK_ACCESS_TOKEN":       _read_env_key("FACEBOOK_ACCESS_TOKEN"),
        "FACEBOOK_PAGE_ID":            _read_env_key("FACEBOOK_PAGE_ID"),
        "LINKEDIN_ACCESS_TOKEN":       _read_env_key("LINKEDIN_ACCESS_TOKEN"),
        "LINKEDIN_PERSON_ID":          _read_env_key("LINKEDIN_PERSON_ID"),
        "TWITTER_BEARER_TOKEN":        _read_env_key("TWITTER_BEARER_TOKEN"),
        "TWITTER_API_KEY":             _read_env_key("TWITTER_API_KEY"),
        "TWITTER_API_SECRET":          _read_env_key("TWITTER_API_SECRET"),
        "TWITTER_ACCESS_TOKEN":        _read_env_key("TWITTER_ACCESS_TOKEN"),
        "TWITTER_ACCESS_TOKEN_SECRET": _read_env_key("TWITTER_ACCESS_TOKEN_SECRET"),
        "TIKTOK_ACCESS_TOKEN":         _read_env_key("TIKTOK_ACCESS_TOKEN"),
        "NOTIFY_EMAIL":                _read_env_key("NOTIFY_EMAIL"),
        "SMTP_EMAIL":                  _read_env_key("SMTP_EMAIL"),
        "SMTP_PASSWORD":               _read_env_key("SMTP_PASSWORD"),
    }
    return render_template("setup.html", token_status=token_status, token_values=token_values)


@bp.route("/token-speichern", methods=["POST"])
def save_token():
    """Write one or more env keys to .env file."""
    data = request.get_json(silent=True) or {}
    allowed_keys = {
        "CLAUDE_API_KEY", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID",
        "FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID", "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_PERSON_ID", "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET", "TWITTER_BEARER_TOKEN",
        "TIKTOK_ACCESS_TOKEN", "NOTIFY_EMAIL", "SMTP_EMAIL", "SMTP_PASSWORD",
    }
    saved = []
    for key, value in data.items():
        if key not in allowed_keys:
            continue
        _write_env_key(key, str(value).strip())
        saved.append(key)
    if not saved:
        return jsonify({"error": "Keine gültigen Keys angegeben"}), 400
    # Reload dotenv so the running process picks up new values immediately
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass
    return jsonify({"ok": True, "saved": saved})


@bp.route("/token-testen", methods=["POST"])
def test_token():
    """Test a platform's token by hitting its API."""
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "").lower()
    config = load_config()

    if platform == "claude":
        result = _test_claude(config["claude"]["api_key"] or "")
    elif platform == "instagram":
        result = _test_instagram(
            config["instagram"]["access_token"] or "",
            config["instagram"]["account_id"] or "")
    elif platform == "facebook":
        result = _test_facebook(config["facebook"]["access_token"] or "")
    elif platform == "linkedin":
        result = _test_linkedin(config["linkedin"]["access_token"] or "")
    elif platform == "twitter":
        result = _test_twitter(config["twitter"]["bearer_token"] or "")
    elif platform == "tiktok":
        result = {"ok": None, "msg": "TikTok-Test nicht automatisch möglich — Token manuell prüfen."}
    else:
        return jsonify({"error": "Unbekannte Plattform"}), 400

    return jsonify(result)


@bp.route("/plattform-pause", methods=["POST"])
def toggle_platform_pause():
    """Pausiert oder reaktiviert eine Plattform ohne den Token zu löschen."""
    data     = request.get_json(silent=True) or {}
    platform = data.get("platform", "").lower()
    paused   = bool(data.get("paused", False))
    if platform not in {"instagram", "facebook", "linkedin", "twitter", "tiktok"}:
        return jsonify({"error": "Unbekannte Plattform"}), 400
    from dashboard.services.variant_service import set_platform_paused
    set_platform_paused(platform, paused)
    return jsonify({"ok": True, "platform": platform, "paused": paused})


@bp.route("/marke/pdf-upload", methods=["POST"])
def pdf_upload():
    if "file" not in request.files:
        return jsonify({"error": "Keine Datei"}), 400
    f = request.files["file"]
    if not f.filename.endswith(".pdf"):
        return jsonify({"error": "Nur PDF-Dateien erlaubt"}), 400

    save_path = PDF_UPLOAD_DIR / f.filename
    f.save(str(save_path))

    config    = load_config()
    extractor = BrandExtractor(config["claude"]["api_key"])

    try:
        facts = extractor.extract_from_pdf(save_path)
        extractor.save_brand_knowledge(facts, source_filename=f.filename)
        return jsonify({"ok": True, "facts": facts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/marke/bestaetigen", methods=["POST"])
def confirm_brand():
    data = request.get_json(silent=True) or {}
    BrandExtractor().confirm_brand_knowledge(data)
    return jsonify({"ok": True})


@bp.route("/submission-importieren", methods=["POST"])
def import_submission():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Ungültiger Dateiname"}), 400
    submissions_root = Path("client/submissions").resolve()
    sub_file = (submissions_root / filename).resolve()
    if not str(sub_file).startswith(str(submissions_root)):
        return jsonify({"error": "Ungültiger Dateiname"}), 400
    if not sub_file.exists():
        return jsonify({"error": "Datei nicht gefunden"}), 404
    try:
        sub_data = json.loads(sub_file.read_text(encoding="utf-8"))
        # Inline mapping (same as form_server._map_submission_to_brand)
        bk = {}
        def _split(val, n=8):
            if not val: return []
            if isinstance(val, list): return [str(x).strip() for x in val if str(x).strip()][:n]
            return [x.strip() for x in str(val).replace("\n",",").replace(";",",").split(",") if x.strip()][:n]
        if sub_data.get("company_name"): bk["brand_name"] = str(sub_data["company_name"]).strip()
        if sub_data.get("slogan"):        bk["slogan"]     = str(sub_data["slogan"]).strip()
        mission = sub_data.get("elevator_pitch") or sub_data.get("company_desc", "")
        if mission: bk["mission"] = str(mission).strip()[:500]
        industry = sub_data.get("industry") or sub_data.get("services", "")
        if industry: bk["industry"] = str(industry).strip()[:200]
        vals = _split(sub_data.get("culture") or sub_data.get("values"), 6)
        if vals: bk["values"] = vals
        usps = _split(sub_data.get("usps"), 5)
        if usps: bk["usp"] = usps
        tone = _split(sub_data.get("words_use"), 8)
        if tone: bk["tone_keywords"] = tone
        avoid = _split(sub_data.get("words_avoid"), 8)
        if avoid: bk["avoid_words"] = avoid
        pillars = _split(sub_data.get("content_pillars"), 8)
        if pillars: bk["content_pillars"] = pillars
        if sub_data.get("forbidden_topics"): bk["forbidden_topics"] = str(sub_data["forbidden_topics"])[:300]
        faq = {}
        name = sub_data.get("company_name", "Wir")
        if sub_data.get("company_desc"):   faq[f"Was macht {name}?"] = str(sub_data["company_desc"])[:300]
        if sub_data.get("faq_clients"):    faq["FAQ (Kunden)"]       = str(sub_data["faq_clients"])[:400]
        if sub_data.get("faq_recruits"):   faq["FAQ (Bewerber)"]     = str(sub_data["faq_recruits"])[:400]
        if faq: bk["faq"] = faq
        for k in ("escalate_name","escalate_contact","ig_handle","contact_email","contact_name"):
            if sub_data.get(k): bk[k] = str(sub_data[k])
        bk["source_submission"] = filename
        bk["imported_at"] = datetime.now().isoformat()
        bk["confirmed_by_user"] = True
        bk_file = Path("client/brand_knowledge.json")
        existing = {}
        if bk_file.exists():
            try: existing = json.loads(bk_file.read_text(encoding="utf-8"))
            except Exception: pass
        existing.update(bk)
        bk_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"ok": True, "brand_name": bk.get("brand_name", "")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
