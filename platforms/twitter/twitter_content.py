import anthropic
from brand.foerderkraft_brand import get_brand_context, get_platform_voice, BRAND

class TwitterContent:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.brand_context = get_brand_context("twitter")
        self.voice = get_platform_voice("twitter")

    def generate_tweet(self, topic):
        """Tweet generieren (max 280 Zeichen)"""
        hashtags = " ".join(self.voice.get("hashtags_permanent", []))
        openings = "\n".join(self.voice.get("example_opening_lines", []))

        prompt = f"""Du schreibst Tweets für {BRAND['name']}.

{self.brand_context}

THEMA: {topic}

Erstelle einen Tweet der:
- Maximal 255 Zeichen hat (Platz für Hashtags lassen)
- Direkt und meinungsstark ist (inspiriert von: {openings})
- Sofort einen Mehrwert liefert oder provoziert nachzudenken
- Mit diesen Hashtags endet: {hashtags}

Antworte NUR mit dem Tweet."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_thread(self, topic, tweet_count=5):
        """Twitter Thread generieren"""
        prompt = f"""Erstelle einen Twitter/X Thread für {BRAND['name']} zum Thema: {topic}

{self.brand_context}

{tweet_count} Tweets die zusammen eine Geschichte oder Erkenntnis vermitteln.

Format:
1/ [Hook - reißt sofort rein]
2/ [Inhalt]
...
{tweet_count}/ [Abschluss mit CTA]

Jeder Tweet max 260 Zeichen. Direkt, prägnant, {BRAND['name']}-typisch.
Antworte NUR mit dem Thread."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_mention(self, mention_text):
        """Auf Mention antworten"""
        prompt = f"""Du bist Social Media Manager von {BRAND['name']} auf Twitter/X.

{self.brand_context}

Mention: {mention_text}

Kurze, schlagfertige Antwort im {BRAND['name']}-Ton (max 200 Zeichen).
Antworte NUR mit der Antwort."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_dm(self, dm_text):
        """Auf DM antworten"""
        prompt = f"""Du bist Kundenservice von {BRAND['name']} auf Twitter/X.

{self.brand_context}

Nachricht: {dm_text}

Kurze, hilfreiche Antwort im Twitter-Ton (max 280 Zeichen).
Antworte NUR mit der Nachricht."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_sales_tip(self):
        """Täglichen Vertriebstipp im Förderkraft-Stil generieren"""
        prompt = f"""Generiere einen Vertriebstipp für {BRAND['name']} auf Twitter/X.

{self.brand_context}

Der Tipp soll:
- Aus echter Door-to-Door Sales Erfahrung kommen
- Direkt umsetzbar sein
- Max 240 Zeichen sein
- Mit einem Emoji starten
- Den Ton von {BRAND['name']} treffen: direkt, selbstbewusst, wertvoll

Antworte NUR mit dem Tipp."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
