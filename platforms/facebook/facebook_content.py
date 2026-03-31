import anthropic
from brand.foerderkraft_brand import get_brand_context, get_platform_voice, BRAND

class FacebookContent:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.brand_context = get_brand_context("facebook")
        self.voice = get_platform_voice("facebook")

    def generate_post(self, topic):
        """Facebook Post generieren"""
        hashtags = " ".join(self.voice.get("hashtags_permanent", []))
        openings = "\n".join(self.voice.get("example_opening_lines", []))
        ctas = "\n".join(self.voice.get("cta_examples", []))

        prompt = f"""Du schreibst Facebook Posts für {BRAND['name']}.

{self.brand_context}

THEMA: {topic}

Erstelle einen Facebook Post der:
- Nahbar und persönlich klingt (inspiriert von: {openings})
- Lokale Verbindung zeigt wo möglich
- Vertrauen in {BRAND['name']} aufbaut
- Engagement fördert (Frage, Reaktion einladen)
- Mit einem dieser CTAs endet: {ctas}
- Diese Hashtags enthält: {hashtags}
- Max 400 Wörter ist

Antworte NUR mit dem Post-Text."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_comment(self, comment_text):
        """Auf Facebook Kommentar antworten"""
        prompt = f"""Du bist Social Media Manager von {BRAND['name']} auf Facebook.

{self.brand_context}

Kommentar: {comment_text}

Antworte kurz, freundlich, nahbar (max 2 Sätze).
Antworte NUR mit der Antwort."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_dm(self, dm_text):
        """Auf Facebook Messenger Nachricht antworten"""
        prompt = f"""Du bist Kundenservice von {BRAND['name']} auf Facebook.

{self.brand_context}

Eingehende Nachricht: {dm_text}

Schreibe eine freundliche, hilfreiche Antwort im Facebook-Ton.
Falls Preisfrage: persönliches Gespräch anbieten.
Falls Jobinteresse: auf Bewerbungsmöglichkeit hinweisen.
Antworte NUR mit der Nachricht."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_ad_copy(self, product_or_service, target_audience):
        """Facebook Anzeigentext generieren"""
        prompt = f"""Erstelle einen Facebook Anzeigentext für {BRAND['name']}.

{self.brand_context}

Produkt/Dienstleistung: {product_or_service}
Zielgruppe: {target_audience}

Der Text soll:
- In den ersten 2 Zeilen Aufmerksamkeit erzeugen
- Den konkreten Nutzen klar benennen
- {BRAND['name']} als vertrauenswürdigen Partner darstellen
- Einen starken CTA haben
- Max 150 Wörter sein

Antworte NUR mit dem Anzeigentext."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
