import anthropic
from brand.foerderkraft_brand import get_brand_context, get_platform_voice, BRAND

class TikTokContent:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.brand_context = get_brand_context("tiktok")
        self.voice = get_platform_voice("tiktok")

    def generate_video_script(self, topic, duration_seconds=60):
        """TikTok Video Script generieren"""
        openings = "\n".join(self.voice.get("example_opening_lines", []))

        prompt = f"""Du schreibst ein TikTok Script für {BRAND['name']}.

{self.brand_context}

THEMA: {topic}
LÄNGE: ca. {duration_seconds} Sekunden

Erstelle ein Script mit:
- Hook in den ersten 3 Sekunden (inspiriert von: {openings})
- Authentischem, energetischem Ton - kein Werbesprech
- Struktur: Hook → Story/Problem → Lösung → CTA
- Konkreten Szenen und was gesagt wird

Format:
[SZENE]: Was zu sehen ist
[SPRECHER]: Was gesagt wird
[OVERLAY]: Eingeblendeter Text (optional)

Antworte NUR mit dem Script."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_caption(self, topic):
        """TikTok Caption und Hashtags generieren"""
        hashtags = " ".join(self.voice.get("hashtags_permanent", []))

        prompt = f"""Erstelle eine TikTok Caption für {BRAND['name']} zum Thema: {topic}

{self.brand_context}

Max 150 Zeichen, neugierig machend.
Diese festen Hashtags: {hashtags} + 4-5 TikTok-spezifische Hashtags.
Antworte NUR mit Caption + Hashtags."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_content_ideas(self, count=10):
        """Content-Ideen für TikTok generieren"""
        pillars = "\n".join(self.voice.get("content_pillars", []))

        prompt = f"""Generiere {count} TikTok Video-Ideen für {BRAND['name']}.

{self.brand_context}

Content-Säulen:
{pillars}

Für jede Idee:
- Kurze Beschreibung
- Hook-Idee für die ersten 3 Sekunden
- Warum es für die Zielgruppe relevant ist

Antworte NUR mit den Ideen als nummerierte Liste."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_comment(self, comment_text):
        """Auf TikTok Kommentar antworten"""
        prompt = f"""Du bist Social Media Manager von {BRAND['name']} auf TikTok.

{self.brand_context}

Kommentar: {comment_text}

Kurze, energetische Antwort (max 1 Satz). Darf Emojis haben.
Antworte NUR mit der Antwort."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
