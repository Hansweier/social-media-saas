import anthropic
from brand.foerderkraft_brand import get_brand_context, get_platform_voice, BRAND

class LinkedInContent:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.brand_context = get_brand_context("linkedin")
        self.voice = get_platform_voice("linkedin")

    def generate_post(self, topic):
        """LinkedIn Post generieren"""
        hashtags = " ".join(self.voice.get("hashtags_permanent", []))
        openings = "\n".join(self.voice.get("example_opening_lines", []))
        ctas = "\n".join(self.voice.get("cta_examples", []))

        prompt = f"""Du schreibst LinkedIn Posts für {BRAND['name']}.

{self.brand_context}

THEMA: {topic}

Erstelle einen LinkedIn Post der:
- Mit einem starken ersten Satz startet (inspiriert von: {openings})
- {BRAND['name']} als Experte im Direktvertrieb positioniert
- Einen echten Mehrwert für den Leser bietet
- Professionell aber nicht steif klingt - Anrede: Sie
- Mit einem dieser CTAs endet (oder ähnlichem): {ctas}
- Diese festen Hashtags enthält + 2-3 thematische: {hashtags}
- Max 1300 Zeichen ist

Antworte NUR mit dem Post-Text."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_outreach_message(self, recipient_name, recipient_role, recipient_company):
        """Personalisierte LinkedIn Kontaktnachricht generieren"""
        prompt = f"""Du schreibst eine LinkedIn Kontaktnachricht für {BRAND['name']}.

{self.brand_context}

Empfänger: {recipient_name}, {recipient_role} bei {recipient_company}

Schreibe eine kurze, persönliche Nachricht (max 300 Zeichen) die:
- Persönlich klingt, nicht wie eine Massenmail
- Den konkreten Mehrwert für {recipient_company} betont
- Zu einem kurzen Gespräch einlädt

Antworte NUR mit der Nachricht."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_comment(self, comment_text):
        """Auf LinkedIn Kommentar antworten"""
        prompt = f"""Du bist Social Media Manager von {BRAND['name']} auf LinkedIn.

{self.brand_context}

Kommentar: {comment_text}

Schreibe eine professionelle, kurze Antwort (max 2 Sätze). Anrede: Sie.
Antworte NUR mit der Antwort."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_dm(self, dm_text):
        """Auf LinkedIn Nachricht antworten"""
        prompt = f"""Du bist Kundenservice von {BRAND['name']} auf LinkedIn.

{self.brand_context}

Eingehende Nachricht: {dm_text}

Schreibe eine professionelle, hilfreiche Antwort. Anrede: Sie.
Falls Interesse an Zusammenarbeit: Erstgespräch anbieten.
Falls Jobinteresse: auf Karrieremöglichkeiten hinweisen.
Antworte NUR mit der Nachricht."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_job_post(self, position="Vertriebsmitarbeiter"):
        """Stellenanzeige generieren"""
        prompt = f"""Erstelle eine LinkedIn Stellenanzeige für {BRAND['name']}.

{self.brand_context}

Position: {position}

Die Anzeige soll:
- Motivierend und authentisch klingen
- Die Unternehmenskultur von {BRAND['name']} widerspiegeln
- Konkrete Vorteile nennen (Provision, Entwicklung, Team)
- Die richtigen Kandidaten ansprechen
- Professionell wirken

Antworte NUR mit der Stellenanzeige."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
