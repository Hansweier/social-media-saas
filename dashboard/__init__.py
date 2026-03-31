"""
Dashboard — Flask Web-App für Sozibot.
Läuft auf Port 5000.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from pathlib import Path

MEDIA_DIR       = Path("client/media")
PROCESSED_DIR   = Path("client/media/processed")
QUEUE_DIR       = Path("client/media/queue")

for d in [MEDIA_DIR, PROCESSED_DIR, QUEUE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def create_app():
    app = Flask(__name__, template_folder="templates")
    import secrets as _secrets
    app.secret_key = os.getenv("SECRET_KEY") or _secrets.token_hex(32)

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template_string
        return render_template_string("""
        <!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
        <title>404 — Seite nicht gefunden</title>
        <style>*{box-sizing:border-box;margin:0;padding:0}
        body{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
        .box{text-align:center;padding:40px}.num{font-size:80px;font-weight:800;color:#e3000b;line-height:1}
        h2{font-size:22px;margin:12px 0 8px}p{color:#8892a4;margin-bottom:24px}
        a{display:inline-block;padding:10px 22px;background:#e3000b;color:white;border-radius:8px;text-decoration:none;font-weight:600}</style>
        </head><body><div class="box">
        <div class="num">404</div>
        <h2>Seite nicht gefunden</h2>
        <p>Diese URL existiert nicht im Dashboard.</p>
        <a href="/">← Zurück zur Übersicht</a>
        </div></body></html>"""), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template_string
        return render_template_string("""
        <!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
        <title>500 — Serverfehler</title>
        <style>*{box-sizing:border-box;margin:0;padding:0}
        body{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
        .box{text-align:center;padding:40px;max-width:500px}.num{font-size:80px;font-weight:800;color:#f87171;line-height:1}
        h2{font-size:22px;margin:12px 0 8px}p{color:#8892a4;margin-bottom:24px;line-height:1.6}
        a{display:inline-block;padding:10px 22px;background:#e3000b;color:white;border-radius:8px;text-decoration:none;font-weight:600}
        .err{font-family:monospace;font-size:12px;background:#1a1d27;padding:12px;border-radius:8px;color:#f87171;text-align:left;margin-bottom:20px;word-break:break-all}</style>
        </head><body><div class="box">
        <div class="num">500</div>
        <h2>Interner Serverfehler</h2>
        <div class="err">{{ error }}</div>
        <p>Der Bot läuft weiter — dies betrifft nur diese eine Seite. Prüfe das Log für Details.</p>
        <a href="/">← Zurück zur Übersicht</a>
        </div></body></html>""", error=str(e)), 500

    # First-run redirect: Schritt 1 → Fragebogen, Schritt 2 → Setup (API Keys)
    @app.before_request
    def first_run_check():
        from flask import request, redirect
        # Routen die ohne Konfiguration erreichbar sein müssen
        _skip = (
            "/einstellungen/setup",
            "/einstellungen/token-speichern",
            "/einstellungen/token-testen",
            "/kunden-vorschau",   # öffentliche Kunden-Vorschau
            "/fragebogen",        # Onboarding — kein API Key nötig
            "/landing",           # öffentliche Landing Page
            "/billing",           # Billing — immer erreichbar
            "/static",
            "/api/",
            "/media/file/",
            "/media/processed/",
        )
        if any(request.path.startswith(p) for p in _skip):
            return None

        # Schritt 1: Wenn noch keine Marke konfiguriert → Fragebogen
        brand_file = Path("client/brand_knowledge.json")
        if not brand_file.exists():
            return redirect("/fragebogen")
        try:
            import json
            bk = json.loads(brand_file.read_text(encoding="utf-8"))
            if not bk.get("confirmed_by_user") and not bk.get("brand_name"):
                return redirect("/fragebogen")
        except Exception:
            pass

        # Schritt 2: Wenn Claude API Key fehlt → Setup Wizard
        from bot.config import load_config
        cfg = load_config()
        api_key = cfg.get("claude", {}).get("api_key") or ""
        if not api_key or "dein" in api_key or not api_key.startswith("sk-ant"):
            return redirect("/einstellungen/setup")
        return None

    @app.context_processor
    def inject_brand():
        try:
            from brand.foerderkraft_brand import get_brand
            b = get_brand()
            return {"brand_name": b.get("name", "Social Media Bot"),
                    "brand_industry": b.get("industry", "")}
        except Exception:
            return {"brand_name": "Social Media Bot", "brand_industry": ""}

    from dashboard.routes.overview  import bp as overview_bp
    from dashboard.routes.calendar  import bp as calendar_bp
    from dashboard.routes.analytics import bp as analytics_bp
    from dashboard.routes.composer  import bp as composer_bp
    from dashboard.routes.media     import bp as media_bp
    from dashboard.routes.api       import bp as api_bp
    from dashboard.routes.approval       import bp as approval_bp
    from dashboard.routes.brand_settings import bp as brand_bp
    from dashboard.routes.preview        import bp as preview_bp
    from dashboard.routes.learning       import bp as learning_bp
    from dashboard.routes.fragebogen     import bp as fragebogen_bp
    from dashboard.routes.landing        import bp as landing_bp
    from dashboard.routes.billing        import bp as billing_bp

    app.register_blueprint(overview_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(composer_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(approval_bp)
    app.register_blueprint(brand_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(fragebogen_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(billing_bp)

    return app
