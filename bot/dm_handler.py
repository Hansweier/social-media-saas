import anthropic
import json
import os
import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
from brand.foerderkraft_brand import get_brand_context, BRAND

log = logging.getLogger(__name__)


def _get_contact_info() -> dict:
    """Lädt Kontaktdaten aus brand_knowledge.json."""
    try:
        from pathlib import Path
        bk = json.loads(Path("client/brand_knowledge.json").read_text(encoding="utf-8"))
        return {
            "jobs_email": bk.get("escalate_contact") or bk.get("contact_email") or "",
            "info_email": bk.get("contact_email") or "",
        }
    except Exception:
        return {"jobs_email": "", "info_email": ""}


class DMHandler:
    """
    Intelligenter DM/Kommentar Handler für alle Plattformen.
    Erkennt die Absicht der Nachricht und antwortet passend.
    """

    def __init__(self, api_key, conversations_file="client/conversations.json", config: dict = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversations_file = conversations_file
        self.config = config or {}
        self.conversations = self._load_conversations()
        brand_name = BRAND.get("name", "uns")

        # Absichten die der Bot erkennt
        self.intents = {
            "job_interesse":      f"Person interessiert sich für eine Stelle bei {brand_name}",
            "auftraggeber":       "Unternehmen interessiert sich als Auftraggeber / Kunde",
            "preis_anfrage":      "Person fragt nach Preisen oder Konditionen",
            "info_anfrage":       f"Allgemeine Frage über {brand_name}",
            "beschwerde":         "Person beschwert sich oder ist unzufrieden",
            "lob":                "Person lobt oder gibt positives Feedback",
            "terminanfrage":      "Person möchte einen Termin vereinbaren",
            "spam":               "Spam, Bot oder irrelevante Nachricht",
            "sonstiges":          "Sonstige Anfrage",
        }

        # Eskalations-Keywords - diese DMs sollen zum echten Menschen weitergeleitet werden
        self.escalation_keywords = [
            "rechtlich", "anwalt", "klage", "beschwerde", "betrug",
            "scam", "abzocke", "stornieren", "kündigen", "notar"
        ]

    def _load_conversations(self):
        if os.path.exists(self.conversations_file):
            try:
                with open(self.conversations_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _notify_escalation(self, platform: str, sender_id: str, message: str):
        """Sendet E-Mail-Alert wenn eine Eskalation erkannt wird."""
        cfg = self.config.get("notify", {})
        smtp_email = cfg.get("smtp_email")
        smtp_pass  = cfg.get("smtp_password")
        to_email   = cfg.get("email")
        if not smtp_email or not smtp_pass or "dein" in str(smtp_pass):
            log.warning(f"[!] ESKALATION auf {platform} von {sender_id}: {message[:80]}... (kein SMTP konfiguriert)")
            return
        try:
            msg = MIMEText(
                f"Plattform: {platform}\nSender: {sender_id}\n\nNachricht:\n{message}\n\n"
                f"→ Dashboard: http://localhost:5000/verlauf/",
                "plain", "utf-8"
            )
            msg["Subject"] = f"[{BRAND.get('name', 'Sozibot')} Bot] ⚠️ Eskalation auf {platform}"
            msg["From"]    = smtp_email
            msg["To"]      = to_email
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as s:
                s.login(smtp_email, smtp_pass)
                s.sendmail(smtp_email, to_email, msg.as_string())
            log.info(f"Eskalations-E-Mail gesendet: {platform}/{sender_id}")
        except Exception as e:
            log.warning(f"Eskalations-E-Mail fehlgeschlagen: {e}")

    def _save_conversations(self):
        os.makedirs(os.path.dirname(self.conversations_file), exist_ok=True)
        with open(self.conversations_file, "w", encoding="utf-8") as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)

    def _log_conversation(self, platform, sender_id, message, intent, response, escalate=False):
        """Konversation speichern"""
        entry = {
            "timestamp": str(datetime.now()),
            "platform": platform,
            "sender_id": sender_id,
            "message": message,
            "intent": intent,
            "response": response,
            "escalate": escalate,
        }
        self.conversations.append(entry)
        self._save_conversations()

    def detect_intent(self, message: str) -> str:
        """Erkennt die Absicht einer Nachricht"""
        prompt = f"""Analysiere diese Nachricht an {BRAND.get('name', 'unser Unternehmen')} und klassifiziere die Absicht:

Nachricht: "{message}"

Mögliche Absichten:
{json.dumps(self.intents, ensure_ascii=False, indent=2)}

Antworte NUR mit dem Schlüssel der passenden Absicht, z.B.: job_interesse"""

        result = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=30,
            messages=[{"role": "user", "content": prompt}]
        )
        intent = result.content[0].text.strip().lower()
        return intent if intent in self.intents else "sonstiges"

    def should_escalate(self, message: str) -> bool:
        """Prüft ob die Nachricht zu einem echten Menschen eskaliert werden soll"""
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in self.escalation_keywords)

    def generate_response(self, message: str, platform: str, conversation_history=None) -> dict:
        """
        Generiert eine intelligente Antwort auf eine DM oder einen Kommentar.
        Gibt zurück: {response, intent, escalate}
        """
        # Eskalation prüfen
        if self.should_escalate(message):
            return {
                "response": "Vielen Dank für deine Nachricht. Wir leiten dein Anliegen direkt an unser Team weiter und melden uns schnellstmöglich persönlich bei dir. 🙏",
                "intent": "eskalation",
                "escalate": True
            }

        # Absicht erkennen
        intent = self.detect_intent(message)

        # Kontext aufbauen
        brand_ctx = get_brand_context(platform)
        history_text = ""
        if conversation_history:
            history_text = "\nBisheriger Gesprächsverlauf:\n" + "\n".join([
                f"{'Kunde' if m['role'] == 'user' else BRAND.get('name', 'Wir')}: {m['content']}"
                for m in conversation_history[-4:]  # Letzte 4 Nachrichten
            ])

        # Ton je nach Absicht
        brand_name = BRAND.get("name", "uns")
        intent_instructions = {
            "job_interesse":  f"Die Person will bei {brand_name} arbeiten. Zeige Begeisterung, erkläre kurz die Vorteile und bitte um Lebenslauf oder lade zu einem Gespräch ein.",
            "auftraggeber":   "Ein potenzieller Auftraggeber. Sei professionell, zeige Mehrwert und biete ein kostenloses Erstgespräch an.",
            "preis_anfrage":  "Erkläre dass Preise individuell sind und biete ein persönliches Gespräch zur Bedarfsanalyse an. Keine konkreten Zahlen nennen.",
            "info_anfrage":   "Beantworte die Frage hilfreich und klar. Verweise auf weitere Infos wenn nötig.",
            "beschwerde":     "Zeige Verständnis, entschuldige dich für die Unannehmlichkeiten, biete Lösung an und eskaliere intern.",
            "lob":            "Bedanke dich herzlich und authentisch. Kurz und persönlich.",
            "terminanfrage":  "Zeige Freude über das Interesse und gib eine E-Mail oder Kalender-Link zum Buchen.",
            "spam":           "Antworte nicht oder mit einer kurzen höflichen Ablehnung.",
            "sonstiges":      "Antworte hilfsbereit und biete an weiterzuhelfen.",
        }

        instruction = intent_instructions.get(intent, intent_instructions["sonstiges"])

        contact    = _get_contact_info()
        jobs_hint  = f"- Falls Job-Interesse: {contact['jobs_email']} erwähnen" if contact["jobs_email"] else ""
        info_hint  = f"- Falls Auftraggeber: {contact['info_email']} erwähnen" if contact["info_email"] else ""
        contact_rules = "\n".join(filter(None, [jobs_hint, info_hint]))

        prompt = f"""Du bist der Social Media Manager von {BRAND['name']} auf {platform.upper()}.

{brand_ctx}
{history_text}

Eingehende Nachricht: "{message}"
Erkannte Absicht: {intent}

Aufgabe: {instruction}

Wichtige Regeln:
- Klinge wie ein echter Mensch, nicht wie ein Bot
- Sei auf den Punkt, nicht zu lang
- Passe den Ton der Plattform an ({platform})
- Keine leeren Floskeln
{contact_rules}

Antworte NUR mit der Nachricht."""

        result = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        response = result.content[0].text.strip()
        return {
            "response": response,
            "intent": intent,
            "escalate": intent == "beschwerde"
        }

    def handle(self, platform: str, sender_id: str, message: str) -> dict:
        """
        Hauptfunktion: Nachricht verarbeiten und Antwort zurückgeben.
        Wird vom Scheduler automatisch aufgerufen.
        """
        # Bisherige Konversation laden
        history = [
            {"role": "user" if c["sender_id"] == sender_id else "assistant", "content": c["message"]}
            for c in self.conversations
            if c["platform"] == platform and c["sender_id"] == sender_id
        ][-6:]  # Letzte 6 Nachrichten

        result = self.generate_response(message, platform, history)

        # Speichern
        self._log_conversation(
            platform=platform,
            sender_id=sender_id,
            message=message,
            intent=result["intent"],
            response=result["response"],
            escalate=result["escalate"]
        )

        if result["escalate"]:
            self._notify_escalation(platform, sender_id, message)

        return result
