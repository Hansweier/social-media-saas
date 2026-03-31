import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def validate_config(config: dict):
    """Prüft kritische Config-Werte beim Start. Gibt Warnungen aus."""
    if not config["claude"]["api_key"]:
        print("FEHLER: CLAUDE_API_KEY fehlt in .env — Bot kann keinen Content generieren!", file=sys.stderr)
        sys.exit(1)
    if not config["claude"]["api_key"].startswith("sk-ant"):
        log.warning("CLAUDE_API_KEY sieht ungültig aus (erwartet: sk-ant...)")

    missing = []
    checks = {
        "instagram": config["instagram"]["access_token"],
        "facebook":  config["facebook"]["access_token"],
        "linkedin":  config["linkedin"]["access_token"],
        "twitter":   config["twitter"]["api_key"],
        "tiktok":    config["tiktok"]["access_token"],
    }
    for p, t in checks.items():
        if not t or "dein" in str(t):
            missing.append(p)
    if missing:
        log.info(f"Plattformen ohne Token (werden übersprungen): {', '.join(missing)}")

    smtp = config["notify"]["smtp_password"]
    if not smtp or "dein" in str(smtp):
        log.info("SMTP nicht konfiguriert — E-Mail-Benachrichtigungen deaktiviert.")


def _build_posting_schedule() -> dict:
    """Leitet {platform: ["HH:MM"]} aus bot_settings.json ab (eine Source of Truth)."""
    try:
        from dashboard.services.variant_service import get_platform_schedules
        schedules = get_platform_schedules()
        return {p: cfg.get("times", ["09:00"]) for p, cfg in schedules.items()}
    except Exception:
        return {
            "instagram": ["09:00", "18:00"],
            "facebook":  ["10:00", "17:00"],
            "linkedin":  ["08:30", "12:00"],
            "twitter":   ["09:00", "13:00", "18:00"],
            "tiktok":    ["15:00", "20:00"],
        }


def load_config():
    return {
        "claude": {
            "api_key": os.getenv("CLAUDE_API_KEY"),
        },
        "instagram": {
            "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN"),
            "account_id":   os.getenv("INSTAGRAM_ACCOUNT_ID"),
        },
        "facebook": {
            "access_token": os.getenv("FACEBOOK_ACCESS_TOKEN"),
            "page_id":      os.getenv("FACEBOOK_PAGE_ID"),
        },
        "linkedin": {
            "access_token": os.getenv("LINKEDIN_ACCESS_TOKEN"),
            "person_id":    os.getenv("LINKEDIN_PERSON_ID"),
        },
        "tiktok": {
            "access_token": os.getenv("TIKTOK_ACCESS_TOKEN"),
        },
        "twitter": {
            "api_key":              os.getenv("TWITTER_API_KEY"),
            "api_secret":           os.getenv("TWITTER_API_SECRET"),
            "access_token":         os.getenv("TWITTER_ACCESS_TOKEN"),
            "access_token_secret":  os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
            "bearer_token":         os.getenv("TWITTER_BEARER_TOKEN"),
        },
        "posting": {
            "schedule": _build_posting_schedule(),
        },
        "notify": {
            "email": os.getenv("NOTIFY_EMAIL", "info@mindrails.de"),
            "smtp_email":    os.getenv("SMTP_EMAIL"),
            "smtp_password": os.getenv("SMTP_PASSWORD"),
        }
    }
