import anthropic
from brand.foerderkraft_brand import get_brand_context, get_platform_voice, BRAND

class InstagramContent:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.brand_context = get_brand_context("instagram")
        self.voice = get_platform_voice("instagram")

    def generate_caption(self, topic, tone=None):
        """Instagram Caption mit Hashtags generieren"""
        tone = tone or self.voice.get("tone")
        hashtags = " ".join(self.voice.get("hashtags_permanent", []))
        openings = "\n".join(self.voice.get("example_opening_lines", []))
        ctas = "\n".join(self.voice.get("cta_examples", []))

        prompt = f"""Du schreibst Instagram Captions für {BRAND['name']}.

{self.brand_context}

THEMA: {topic}

Erstelle eine Instagram Caption die:
- Mit einem starken Hook startet (inspiriert von diesen Beispielen: {openings})
- Den Ton trifft: {tone}
- Authentisch und modern klingt - KEIN Werbesprech
- Einen dieser CTAs enthält (oder ähnliches): {ctas}
- Mit diesen festen Hashtags endet + 8-10 thematische Hashtags: {hashtags}
- Max 300 Wörter ist

Antworte NUR mit der Caption."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_story_text(self, topic):
        """Text für Instagram Story generieren"""
        prompt = f"""Erstelle kurzen Story-Text für {BRAND['name']} auf Instagram.

{self.brand_context}

THEMA: {topic}

Max 50 Wörter, knackig, neugierig machend oder zum Handeln auffordernd.
Antworte NUR mit dem Story-Text."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_comment(self, comment_text):
        """Auf Instagram Kommentar antworten"""
        prompt = f"""Du bist Social Media Manager von {BRAND['name']} auf Instagram.

{self.brand_context}

Kommentar: {comment_text}

Antworte kurz, freundlich, authentisch (max 1-2 Sätze). Darf Emojis haben.
Antworte NUR mit der Antwort."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_dm(self, dm_text):
        """Auf Instagram DM antworten"""
        prompt = f"""Du bist Kundenservice von {BRAND['name']} auf Instagram.

{self.brand_context}

Eingehende Nachricht: {dm_text}

Schreibe eine freundliche, hilfreiche Antwort im Instagram-Ton.
Falls es um Jobs geht: auf Bewerbung hinweisen.
Falls es um Zusammenarbeit geht: Erstgespräch anbieten.
Antworte NUR mit der Nachricht."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_hashtags(self, topic, count=15):
        """Hashtags generieren"""
        fixed = " ".join(self.voice.get("hashtags_permanent", []))
        prompt = f"""Generiere {count} Instagram Hashtags für {BRAND['name']} zum Thema: {topic}

Direktvertrieb/Sales Kontext. Mix aus groß, mittel, Nische.
Diese festen Hashtags immer dabei: {fixed}
Antworte NUR mit den Hashtags, durch Leerzeichen getrennt."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
