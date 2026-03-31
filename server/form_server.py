"""
Lokaler Formular-Server für das Kunden-Onboarding.

Der Kunde öffnet: http://localhost:8080/fragebogen
Füllt das Formular aus, drückt "Abschicken"
Die Antworten landen in: client/submissions/

Starten: python server/form_server.py
"""

import http.server
import json
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

PORT = 5050
# Use absolute paths so the server works regardless of CWD
_PROJECT_ROOT   = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = _PROJECT_ROOT / "client" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

LABELS = {
    "company_name": "Firmenname", "website": "Website", "founded": "Gegründet",
    "employees": "Mitarbeiter", "locations": "Standorte", "slogan": "Slogan",
    "company_desc": "Beschreibung", "company_story": "Geschichte", "culture": "Kultur",
    "elevator_pitch": "Elevator Pitch", "usps": "USPs", "numbers": "Zahlen & Erfolge",
    "objections": "Einwände & Antworten", "color_hex": "Farben", "selected_font": "Schriftart",
    "visual_inspo": "Visuell inspiriert von", "voice_good": "On-Brand Beispiel",
    "voice_bad": "Off-Brand Beispiel", "words_use": "Immer nutzen", "words_avoid": "Niemals nutzen",
    "services": "Dienstleistungen", "case_studies": "Erfolgsgeschichten",
    "faq_clients": "FAQ Auftraggeber", "faq_recruits": "FAQ Bewerber",
    "escalate_name": "Eskalation Name", "escalate_contact": "Eskalation Kontakt",
    "email_clients": "E-Mail Auftraggeber", "email_jobs": "E-Mail Jobs",
    "content_pillars": "Content-Säulen", "forbidden_topics": "Verbotene Themen",
    "ig_handle": "Instagram", "li_url": "LinkedIn", "fb_url": "Facebook",
    "tt_handle": "TikTok", "tw_handle": "Twitter",
    "contact_name": "Ansprechpartner", "contact_role": "Position",
    "contact_email": "E-Mail Kontakt", "contact_phone": "Telefon", "notes": "Anmerkungen",
}

BRAND_KNOWLEDGE_FILE = _PROJECT_ROOT / "client" / "brand_knowledge.json"

def _split_field(val, max_items=8):
    """Split a form field (string or list) into a clean list."""
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()][:max_items]
    return [x.strip() for x in str(val).replace("\n", ",").replace(";", ",").split(",") if x.strip()][:max_items]

def _map_submission_to_brand(data: dict, filename: str) -> dict:
    """Maps questionnaire answers to brand_knowledge.json structure."""
    bk = {}
    if data.get("company_name"):
        bk["brand_name"] = str(data["company_name"]).strip()
    if data.get("slogan"):
        bk["slogan"] = str(data["slogan"]).strip()
    mission = data.get("elevator_pitch") or data.get("company_desc", "")
    if mission:
        bk["mission"] = str(mission).strip()[:500]
    industry = data.get("industry") or data.get("services", "")
    if industry:
        bk["industry"] = str(industry).strip()[:200]
    vals = _split_field(data.get("culture") or data.get("values"), 6)
    if vals:
        bk["values"] = vals
    usps = _split_field(data.get("usps"), 5)
    if usps:
        bk["usp"] = usps
    tone = _split_field(data.get("words_use"), 8)
    if tone:
        bk["tone_keywords"] = tone
    avoid = _split_field(data.get("words_avoid"), 8)
    if avoid:
        bk["avoid_words"] = avoid
    pillars = _split_field(data.get("content_pillars"), 8)
    if pillars:
        bk["content_pillars"] = pillars
    if data.get("forbidden_topics"):
        bk["forbidden_topics"] = str(data["forbidden_topics"])[:300]
    # FAQ
    faq = {}
    name = data.get("company_name", "Wir")
    if data.get("company_desc"):
        faq[f"Was macht {name}?"] = str(data["company_desc"])[:300]
    if data.get("faq_clients"):
        faq["Häufige Fragen (Kunden)"] = str(data["faq_clients"])[:400]
    if data.get("faq_recruits"):
        faq["Häufige Fragen (Bewerber)"] = str(data["faq_recruits"])[:400]
    if faq:
        bk["faq"] = faq
    if data.get("escalate_name"):
        bk["escalate_name"] = str(data["escalate_name"])
    if data.get("escalate_contact"):
        bk["escalate_contact"] = str(data["escalate_contact"])
    if data.get("voice_good"):
        bk["voice_good_example"] = str(data["voice_good"])[:300]
    if data.get("ig_handle"):
        bk["ig_handle"] = str(data["ig_handle"])
    if data.get("contact_email"):
        bk["contact_email"] = str(data["contact_email"])
    if data.get("contact_name"):
        bk["contact_name"] = str(data["contact_name"])
    bk["source_submission"] = filename
    bk["imported_at"] = datetime.now().isoformat()
    bk["confirmed_by_user"] = True
    # Merge with existing brand_knowledge.json
    existing = {}
    if BRAND_KNOWLEDGE_FILE.exists():
        try:
            existing = json.loads(BRAND_KNOWLEDGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing.update(bk)
    BRAND_KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BRAND_KNOWLEDGE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [Brand] Marken-Konfig aktualisiert: {bk.get('brand_name', '?')}")
    return bk

def send_notification_email(data: dict, filename: str):
    """Sendet eine E-Mail mit den Fragebogen-Antworten."""
    smtp_email    = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    notify_email  = os.getenv("NOTIFY_EMAIL", "")

    if not smtp_email or not smtp_password or not notify_email or "dein_app" in smtp_password:
        print("  [E-Mail] Kein SMTP konfiguriert — E-Mail übersprungen.")
        print("  [E-Mail] Trage SMTP_EMAIL + SMTP_PASSWORD + NOTIFY_EMAIL in die .env Datei ein.")
        return

    company = data.get("company_name", "Unbekannt")
    contact = data.get("contact_name", "")
    submitted = data.get("_submitted_at", "")[:16].replace("T", " ")

    # HTML E-Mail aufbauen
    skip = {"_submitted_at", "_filename", "_version", "_exported_at"}
    rows_html = ""
    for key, value in data.items():
        if key in skip or not value or value in ("", [], {}):
            continue
        label = LABELS.get(key, key.replace("_", " ").title())
        if isinstance(value, list):
            val_str = ", ".join(value)
        else:
            val_str = str(value).replace("\n", "<br>")
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;font-size:12px;font-weight:700;color:#94a3b8;
                     text-transform:uppercase;white-space:nowrap;vertical-align:top;
                     border-bottom:1px solid #f1f5f9">{label}</td>
          <td style="padding:8px 12px;font-size:14px;color:#1e293b;
                     border-bottom:1px solid #f1f5f9;line-height:1.6">{val_str}</td>
        </tr>"""

    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:700px;margin:0 auto;background:#f8fafc;padding:32px 16px">
      <div style="background:linear-gradient(135deg,#0f172a,#1e1b4b);border-radius:12px;padding:32px;margin-bottom:20px;color:white">
        <div style="font-size:11px;letter-spacing:2px;color:#a5b4fc;margin-bottom:8px">NEUER ONBOARDING FRAGEBOGEN</div>
        <h1 style="margin:0 0 8px;font-size:24px">{company}</h1>
        <p style="margin:0;color:#c7d2fe;font-size:14px">{contact} &nbsp;·&nbsp; Eingegangen: {submitted}</p>
      </div>
      <div style="background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)">
        <table style="width:100%;border-collapse:collapse">{rows_html}</table>
      </div>
      <p style="text-align:center;font-size:12px;color:#94a3b8;margin-top:20px">
        Datei gespeichert als: {filename}<br>
        Sozibot — KI Social Media System
      </p>
    </div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Neuer Onboarding-Fragebogen: {company}"
    msg["From"]    = smtp_email
    msg["To"]      = notify_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, notify_email, msg.as_bytes())
        print(f"  [E-Mail] Erfolgreich gesendet an {notify_email}")
    except Exception as e:
        print(f"  [E-Mail] Fehler: {e}")


class FormHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Konsolenausgabe unterdrücken

    def do_GET(self):
        if self.path == "/":
            self._serve_landing()
        elif self.path == "/fragebogen":
            self._serve_form()
        elif self.path == "/submissions":
            self._serve_submissions_list()
        elif self.path.startswith("/submission/"):
            filename = self.path.split("/submission/")[1]
            self._serve_submission(filename)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/submit":
            self._handle_submission()
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _serve_landing(self):
        html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Social Media Bot — KI-gestützte Social-Media-Automatisierung</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0f1e;
    --surface: #111827;
    --surface2: #1a2234;
    --border: rgba(255,255,255,.08);
    --text: #f1f5f9;
    --muted: #8892a4;
    --accent: #6366f1;
    --accent2: #8b5cf6;
    --blue: #3b82f6;
    --green: #22c55e;
  }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  a { color: inherit; text-decoration: none; }

  /* Header */
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 40px; border-bottom: 1px solid var(--border);
    background: rgba(10,15,30,.8); backdrop-filter: blur(12px);
    position: sticky; top: 0; z-index: 100;
  }
  .logo { display: flex; align-items: center; gap: 12px; }
  .logo-icon {
    width: 38px; height: 38px; background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius: 10px; display: flex; align-items: center; justify-content: center;
    font-size: 20px;
  }
  .logo-name { font-size: 18px; font-weight: 700; }
  .btn-cta {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white; padding: 10px 24px; border-radius: 8px; font-weight: 600;
    font-size: 14px; transition: opacity .2s; cursor: pointer; border: none;
  }
  .btn-cta:hover { opacity: .88; }
  .btn-outline {
    border: 1px solid var(--border); color: var(--text); padding: 10px 20px;
    border-radius: 8px; font-weight: 500; font-size: 14px; transition: border-color .2s;
  }
  .btn-outline:hover { border-color: var(--accent); color: var(--accent); }

  /* Hero */
  .hero {
    text-align: center; padding: 100px 24px 80px;
    background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(99,102,241,.15), transparent);
  }
  .hero-badge {
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(99,102,241,.12); border: 1px solid rgba(99,102,241,.3);
    border-radius: 99px; padding: 6px 16px; font-size: 13px; color: #a5b4fc;
    margin-bottom: 28px;
  }
  .hero h1 {
    font-size: clamp(32px, 5vw, 60px); font-weight: 800; line-height: 1.15;
    margin-bottom: 20px; letter-spacing: -.02em;
  }
  .hero h1 span { background: linear-gradient(135deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
  .hero p { font-size: 18px; color: var(--muted); max-width: 560px; margin: 0 auto 40px; line-height: 1.6; }
  .hero-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
  .btn-hero {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white; padding: 14px 32px; border-radius: 10px; font-weight: 700;
    font-size: 16px; transition: transform .2s, opacity .2s;
  }
  .btn-hero:hover { transform: translateY(-2px); opacity: .9; }

  /* Section */
  section { padding: 80px 24px; max-width: 1100px; margin: 0 auto; }
  .section-label { font-size: 12px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin-bottom: 12px; }
  .section-title { font-size: clamp(24px, 3vw, 38px); font-weight: 800; margin-bottom: 16px; }
  .section-sub { font-size: 16px; color: var(--muted); max-width: 520px; line-height: 1.6; }

  /* Steps */
  .steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 24px; margin-top: 48px; }
  .step-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
    padding: 28px; position: relative; overflow: hidden; transition: border-color .2s;
  }
  .step-card:hover { border-color: rgba(99,102,241,.4); }
  .step-num {
    font-size: 48px; font-weight: 900; color: rgba(99,102,241,.15);
    position: absolute; right: 20px; top: 12px; line-height: 1;
  }
  .step-icon { font-size: 32px; margin-bottom: 16px; }
  .step-title { font-size: 17px; font-weight: 700; margin-bottom: 8px; }
  .step-desc { font-size: 14px; color: var(--muted); line-height: 1.6; }

  /* Features */
  .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-top: 48px; }
  .feature-card {
    background: var(--surface2); border: 1px solid var(--border); border-radius: 14px;
    padding: 24px; transition: transform .2s, border-color .2s;
  }
  .feature-card:hover { transform: translateY(-3px); border-color: rgba(99,102,241,.3); }
  .feature-icon { font-size: 28px; margin-bottom: 14px; }
  .feature-name { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
  .feature-desc { font-size: 13px; color: var(--muted); line-height: 1.55; }

  /* CTA Section */
  .cta-section {
    text-align: center; padding: 80px 24px;
    background: linear-gradient(135deg, rgba(99,102,241,.08), rgba(139,92,246,.08));
    border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
  }
  .cta-section h2 { font-size: clamp(24px, 3vw, 36px); font-weight: 800; margin-bottom: 16px; }
  .cta-section p { font-size: 16px; color: var(--muted); margin-bottom: 36px; }

  /* Footer */
  footer {
    text-align: center; padding: 32px 24px; color: var(--muted);
    font-size: 13px; border-top: 1px solid var(--border);
  }
  footer a { color: var(--accent); }

  @media (max-width: 600px) {
    header { padding: 16px 20px; }
    .hero { padding: 64px 20px 60px; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">🤖</div>
    <div class="logo-name">Social Media Bot</div>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <a href="/fragebogen" class="btn-cta">Jetzt starten →</a>
  </div>
</header>

<div class="hero">
  <div class="hero-badge">
    <span>✨</span>
    <span>KI-gestützte Social-Media-Automatisierung</span>
  </div>
  <h1>Automatisiere deinen<br><span>Social Media Auftritt</span><br>mit KI</h1>
  <p>Dein persönlicher KI-Bot postet täglich auf Instagram, LinkedIn, Facebook, TikTok und Twitter — vollständig auf deine Marke zugeschnitten.</p>
  <div class="hero-actions">
    <a href="/fragebogen" class="btn-hero">📋 Fragebogen jetzt ausfüllen</a>
  </div>
</div>

<section>
  <div style="text-align:center;margin-bottom:0">
    <div class="section-label">So funktioniert es</div>
    <div class="section-title">In 3 Schritten live</div>
    <div class="section-sub" style="margin:0 auto">Vom Fragebogen zum automatisch postenden KI-Bot — ohne technisches Vorwissen.</div>
  </div>
  <div class="steps">
    <div class="step-card">
      <div class="step-num">1</div>
      <div class="step-icon">📋</div>
      <div class="step-title">Fragebogen ausfüllen</div>
      <div class="step-desc">Beantworte einmalig Fragen zu deiner Marke, deinen Werten, deiner Zielgruppe und deinem Stil. Dauert ca. 15–20 Minuten.</div>
    </div>
    <div class="step-card">
      <div class="step-num">2</div>
      <div class="step-icon">⚙️</div>
      <div class="step-title">Bot wird automatisch konfiguriert</div>
      <div class="step-desc">Deine Antworten werden sofort verarbeitet und der Bot auf deine Markenidentität abgestimmt — vollautomatisch.</div>
    </div>
    <div class="step-card">
      <div class="step-num">3</div>
      <div class="step-icon">🚀</div>
      <div class="step-title">KI postet für dich</div>
      <div class="step-desc">Der Bot generiert täglich maßgeschneiderte Posts und veröffentlicht sie automatisch auf allen deinen Plattformen.</div>
    </div>
  </div>
</section>

<section style="padding-top:0">
  <div style="text-align:center;margin-bottom:0">
    <div class="section-label">Features</div>
    <div class="section-title">Alles was du brauchst</div>
    <div class="section-sub" style="margin:0 auto">Ein vollständiges System für professionelles Social-Media-Management.</div>
  </div>
  <div class="features-grid">
    <div class="feature-card">
      <div class="feature-icon">🧠</div>
      <div class="feature-name">Claude AI</div>
      <div class="feature-desc">Hochwertige Texte durch Anthropic Claude — versteht Kontext, Ton und Markenstimme besser als alle anderen KI-Modelle.</div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">📱</div>
      <div class="feature-name">5 Plattformen</div>
      <div class="feature-desc">Instagram, LinkedIn, Facebook, TikTok und Twitter — jede Plattform bekommt eigenen, plattformgerechten Content.</div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🎨</div>
      <div class="feature-name">Brand-Aware</div>
      <div class="feature-desc">Der Bot kennt deine Werte, deinen Stil, deine Hashtags und deine Sprache — jeder Post klingt wie du.</div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🤝</div>
      <div class="feature-name">Co-Pilot & Auto-Pilot</div>
      <div class="feature-desc">Wähle zwischen manuellem Freigabe-Workflow oder vollautomatischem Posting — je nach deinem Vertrauen und Kontrollanspruch.</div>
    </div>
  </div>
</section>

<div class="cta-section">
  <h2>Bereit, Social Media zu automatisieren?</h2>
  <p>Fülle jetzt den Onboarding-Fragebogen aus und dein Bot ist in wenigen Minuten einsatzbereit.</p>
  <a href="/fragebogen" class="btn-hero" style="display:inline-block">📋 Fragebogen jetzt ausfüllen →</a>
</div>

<footer>
  <p>Social Media Bot &nbsp;·&nbsp; KI-gestützte Automatisierung &nbsp;·&nbsp;
  <a href="/fragebogen">Fragebogen starten →</a></p>
</footer>

</body>
</html>"""
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(encoded))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_form(self):
        form_path = _PROJECT_ROOT / "client" / "fragebogen_foerderkraft.html"
        if not form_path.exists():
            self.send_response(404)
            self.end_headers()
            return
        with open(form_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _handle_submission(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            return

        # Speichern
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        company = data.get("company_name", "unbekannt").replace(" ", "_").replace("/", "-")[:30]
        filename = f"{timestamp}_{company}.json"
        filepath = SUBMISSIONS_DIR / filename

        data["_submitted_at"] = datetime.now().isoformat()
        data["_filename"] = filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Erfolgsmeldung in Konsole
        print(f"\n{'='*50}")
        print(f"  NEUE EINREICHUNG!")
        print(f"  Firma:  {data.get('company_name','?')}")
        print(f"  Kontakt: {data.get('contact_name','?')} ({data.get('contact_email','?')})")
        print(f"  Datei:  client/submissions/{filename}")
        print(f"  Anzeigen: http://localhost:{PORT}/submissions")
        print(f"{'='*50}\n")

        # Auto-import brand settings from submission
        try:
            _map_submission_to_brand(data, filename)
        except Exception as e:
            print(f"  [Brand] Import fehlgeschlagen: {e}")

        # E-Mail im Hintergrund senden
        threading.Thread(target=send_notification_email, args=(data, filename), daemon=True).start()

        # CORS Header
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "file": filename}).encode())

    def _serve_submissions_list(self):
        """Übersicht aller eingegangenen Fragebögen"""
        files = sorted(SUBMISSIONS_DIR.glob("*.json"), reverse=True)
        submissions = []
        for f in files:
            try:
                with open(f, encoding="utf-8") as fp:
                    d = json.load(fp)
                submissions.append({
                    "file": f.name,
                    "company": d.get("company_name", "Unbekannt"),
                    "contact": d.get("contact_name", ""),
                    "email": d.get("contact_email", ""),
                    "submitted": d.get("_submitted_at", "")[:16].replace("T", " "),
                })
            except Exception:
                pass

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Eingegangene Fragebögen</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background:#f1f5f9; margin:0; padding:40px; }}
  h1 {{ color:#0f172a; margin-bottom:8px; }}
  p {{ color:#64748b; margin-bottom:30px; }}
  .card {{ background:white; border-radius:12px; padding:20px 24px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,.08); display:flex; justify-content:space-between; align-items:center; }}
  .card h3 {{ margin:0 0 4px; color:#0f172a; font-size:16px; }}
  .card p {{ margin:0; color:#64748b; font-size:13px; }}
  a.btn {{ background:#6366f1; color:white; padding:8px 18px; border-radius:6px; text-decoration:none; font-size:13px; font-weight:600; }}
  a.btn:hover {{ background:#4f46e5; }}
  .empty {{ text-align:center; padding:60px; color:#94a3b8; }}
</style>
</head>
<body>
<h1>Eingegangene Onboarding-Fragebögen</h1>
<p>{len(submissions)} Einreichung(en) · <a href="/fragebogen">Formular ansehen</a> &nbsp;·&nbsp; <a href="http://localhost:5000/" style="color:#6366f1;font-weight:600">→ Dashboard öffnen</a></p>
"""
        if not submissions:
            html += '<div class="empty">Noch keine Einreichungen eingegangen.</div>'
        else:
            for s in submissions:
                html += f"""
<div class="card">
  <div>
    <h3>{s['company']}</h3>
    <p>{s['contact']} · {s['email']} · Eingegangen: {s['submitted']}</p>
  </div>
  <a class="btn" href="/submission/{s['file']}">Antworten ansehen</a>
</div>"""

        html += "</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_submission(self, filename):
        """Einzelne Einreichung anzeigen"""
        filepath = SUBMISSIONS_DIR / filename
        if not filepath.exists():
            self.send_response(404)
            self.end_headers()
            return

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        skip_keys = {"_submitted_at", "_filename", "_version", "_exported_at"}
        labels = {
            "company_name": "Firmenname", "website": "Website", "founded": "Gegründet",
            "employees": "Mitarbeiter", "locations": "Standorte", "slogan": "Slogan",
            "company_desc": "Beschreibung", "company_story": "Geschichte", "culture": "Kultur",
            "elevator_pitch": "Elevator Pitch", "usps": "USPs", "numbers": "Zahlen/Erfolge",
            "objections": "Einwände & Antworten", "color_hex": "Farben", "selected_font": "Schriftart",
            "visual_inspo": "Visuell inspiriert von", "visual_dont": "Visuell NICHT so",
            "assets_link": "Asset-Link", "words_use": "Immer nutzen", "words_avoid": "Niemals nutzen",
            "voice_good": "On-Brand Beispiel", "voice_bad": "Off-Brand Beispiel",
            "font_custom": "Eigene Schriftart", "good_posts": "Gute Posts",
            "services": "Dienstleistungen", "industry_other": "Weitere Branchen",
            "pricing_model": "Preismodell", "min_order": "Mindestauftrag",
            "case_studies": "Erfolgsgeschichten", "comp1_name": "Wettbewerber 1",
            "comp2_name": "Wettbewerber 2", "comp3_name": "Wettbewerber 3",
            "comp_dont": "Über Wettbewerb nicht sagen", "trends": "Branchentrends",
            "content_pillars": "Content-Säulen", "mix_info": "Mix: Informativ",
            "mix_promo": "Mix: Werbend", "mix_entertain": "Mix: Unterhaltung",
            "seasonal": "Saisonale Themen", "forbidden_topics": "Verbotene Themen",
            "faq_clients": "FAQ Auftraggeber", "faq_recruits": "FAQ Bewerber",
            "escalate_name": "Eskalation Kontakt", "escalate_contact": "Eskalation Kontakt Info",
            "email_clients": "E-Mail Auftraggeber", "email_jobs": "E-Mail Jobs",
            "ig_handle": "Instagram", "li_url": "LinkedIn", "fb_url": "Facebook",
            "tt_handle": "TikTok", "tw_handle": "Twitter",
            "goal_followers": "Follower Ziel", "goal_leads": "Leads Ziel",
            "goal_applications": "Bewerbungen Ziel", "no_post_times": "Nicht posten wann",
            "contact_name": "Ansprechpartner", "contact_role": "Position",
            "contact_email": "E-Mail", "contact_phone": "Telefon", "notes": "Anmerkungen",
            "p1_industry": "Auftraggeber Branche", "p1_title": "Auftraggeber Titel",
            "p1_pain": "Auftraggeber Problem", "p1_convince": "Was überzeugt Auftraggeber",
            "p2_age": "Recruit Alter", "p2_edu": "Recruit Bildung",
            "p2_motive": "Recruit Motivation", "p2_fears": "Recruit Ängste",
        }

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>{data.get('company_name','Fragebogen')} — Onboarding</title>
<style>
  body {{ font-family:'Segoe UI',sans-serif; background:#f1f5f9; margin:0; padding:40px; }}
  .top {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; }}
  h1 {{ color:#0f172a; font-size:24px; }}
  .meta {{ color:#64748b; font-size:13px; margin-top:4px; }}
  a.back {{ color:#6366f1; text-decoration:none; font-size:14px; }}
  .section {{ background:white; border-radius:12px; padding:24px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,.06); }}
  .row {{ padding:10px 0; border-bottom:1px solid #f1f5f9; display:flex; gap:20px; }}
  .row:last-child {{ border:none; }}
  .label {{ font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:.5px; min-width:180px; flex-shrink:0; }}
  .value {{ font-size:14px; color:#1e293b; white-space:pre-wrap; line-height:1.6; }}
  .value.list {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .tag {{ background:#eef2ff; color:#4f46e5; padding:3px 10px; border-radius:99px; font-size:12px; font-weight:600; }}
  .empty {{ color:#cbd5e1; font-style:italic; }}
  .btn {{ background:#6366f1; color:white; padding:8px 18px; border-radius:6px; text-decoration:none; font-size:13px; font-weight:600; cursor:pointer; border:none; }}
</style>
</head>
<body>
<div class="top">
  <div>
    <h1>{data.get('company_name','Fragebogen-Einreichung')}</h1>
    <div class="meta">Eingegangen: {data.get('_submitted_at','')[:16].replace('T',' ')} &nbsp;·&nbsp; {data.get('contact_name','')} &nbsp;·&nbsp; {data.get('contact_email','')}</div>
  </div>
  <div style="display:flex;gap:12px;align-items:center">
    <a href="/submissions" class="back">← Alle Einreichungen</a>
    <button class="btn" onclick="downloadJSON()">JSON herunterladen</button>
  </div>
</div>
<div class="section">
"""
        for key, value in data.items():
            if key in skip_keys:
                continue
            if not value or value == "" or value == [] or value == {}:
                continue
            label = labels.get(key, key.replace("_", " ").title())
            if isinstance(value, list):
                html += f'<div class="row"><div class="label">{label}</div><div class="value list">'
                for item in value:
                    html += f'<span class="tag">{item}</span>'
                html += '</div></div>'
            else:
                html += f'<div class="row"><div class="label">{label}</div><div class="value">{str(value)}</div></div>'

        html += f"""</div>
<script>
function downloadJSON() {{
  const data = {json.dumps(data, ensure_ascii=False)};
  const blob = new Blob([JSON.stringify(data,null,2)], {{type:'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '{filename}';
  a.click();
}}
</script>
</body></html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def run_server(port=PORT):
    """Startet den Formular-Server (kann aus anderen Modulen aufgerufen werden)."""
    try:
        with http.server.HTTPServer(("", port), FormHandler) as httpd:
            print(f"\n  Formular-Server läuft auf Port {port}")
            httpd.serve_forever()
    except OSError:
        print(f"Port {port} bereits belegt — Formular-Server übersprungen.")


if __name__ == "__main__":
    try:
        print(f"\n{'='*50}")
        print(f"  Formular-Server läuft!")
        print(f"  Formular:      http://localhost:{PORT}/fragebogen")
        print(f"  Einreichungen: http://localhost:{PORT}/submissions")
        print(f"  Stoppen: CTRL+C")
        print(f"{'='*50}\n")
        run_server()
    except KeyboardInterrupt:
        print("\nServer gestoppt.")
