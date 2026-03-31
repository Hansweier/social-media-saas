"""
start_bot.py — Ein Befehl, alles startet.

Startet:
  - Social Media Bot (Scheduler + Poster + Engagement)
  - Formular-Server (Port 5050)

Benutze: python start_bot.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import threading
import logging

# ─── Pfad einrichten ─────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.config import load_config, validate_config
from bot.scheduler import Scheduler

log = logging.getLogger(__name__)


def start_form_server():
    """Formular-Server in eigenem Thread starten."""
    try:
        server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server")
        if server_dir not in sys.path:
            sys.path.insert(0, server_dir)
        from form_server import run_server
        run_server()
    except Exception as e:
        log.warning(f"Formular-Server konnte nicht gestartet werden: {e}")


def start_dashboard():
    """Flask Dashboard in eigenem Thread starten."""
    try:
        from dashboard import create_app
        app = create_app()
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    except Exception as e:
        log.warning(f"Dashboard konnte nicht gestartet werden: {e}")


def print_banner():
    try:
        from brand.foerderkraft_brand import get_brand
        brand_name = get_brand().get("name", "Sozibot")
    except Exception:
        brand_name = "Sozibot"
    print()
    print("=" * 60)
    print(f"  {brand_name.upper()} — SOCIAL MEDIA BOT")
    print("  Powered by Sozibot · Claude AI")
    print("=" * 60)
    print()
    print("  Dashboard:        http://localhost:5000")
    print("  Kunden einrichten: http://localhost:5000/fragebogen")
    print("  Kunden-Vorschau:  http://localhost:5000/kunden-vorschau/")
    print("  Plattformen:      Instagram | Facebook | LinkedIn | Twitter | TikTok")
    print()
    print("  Drücke CTRL+C zum Beenden.")
    print("=" * 60)
    print()


def check_config(config: dict) -> bool:
    """Prüft welche Plattformen konfiguriert sind."""
    active = []
    inactive = []

    checks = {
        "instagram": config["instagram"]["access_token"],
        "facebook":  config["facebook"]["access_token"],
        "linkedin":  config["linkedin"]["access_token"],
        "twitter":   config["twitter"]["api_key"],
        "tiktok":    config["tiktok"]["access_token"],
    }

    for platform, token in checks.items():
        if token and "dein" not in token:
            active.append(platform)
        else:
            inactive.append(platform)

    if not config["claude"]["api_key"]:
        print("FEHLER: CLAUDE_API_KEY fehlt in .env!")
        return False

    print("Aktive Plattformen:   " + (", ".join(active) if active else "keine"))
    if inactive:
        print("Nicht konfiguriert:   " + ", ".join(inactive) + "  (Token in .env eintragen)")
    print()
    return True


if __name__ == "__main__":
    print_banner()
    config = load_config()

    if not check_config(config):
        sys.exit(1)
    validate_config(config)

    # Dashboard als Hintergrund-Thread
    dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
    dashboard_thread.start()

    # Bot starten (blockierend)
    bot = Scheduler(config)
    bot.run()
