import anthropic

class AIGenerator:
    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_caption(self, topic, tone="professionell", language="Deutsch"):
        """Instagram Caption mit Hashtags generieren"""
        prompt = f"""Erstelle eine Instagram Caption zum Thema: {topic}

Ton: {tone}
Sprache: {language}

Die Caption soll:
- Ansprechend und authentisch klingen
- Einen Call-to-Action enthalten
- 5-10 passende Hashtags am Ende haben
- Nicht länger als 300 Wörter sein

Antworte NUR mit der Caption, ohne Erklärungen."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_comment(self, comment_text, account_context=""):
        """KI-Antwort auf einen Kommentar generieren"""
        prompt = f"""Du bist ein Social Media Manager.

Kontext über den Account: {account_context}
Kommentar: {comment_text}

Schreibe eine kurze, freundliche Antwort auf diesen Kommentar (max 2 Sätze).
Antworte NUR mit der Antwort, ohne Erklärungen."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def reply_to_dm(self, dm_text, account_context="", faq=""):
        """KI-Antwort auf eine DM generieren"""
        prompt = f"""Du bist ein freundlicher Kundenservice-Assistent für einen Instagram Account.

Kontext über den Account/Business: {account_context}
Häufige Fragen & Antworten: {faq}
Eingehende Nachricht: {dm_text}

Schreibe eine hilfreiche, freundliche Antwort.
Wenn du die Frage nicht beantworten kannst, sage dass du die Anfrage weiterleitest.
Antworte NUR mit der Nachricht, ohne Erklärungen."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def generate_hashtags(self, topic, count=15):
        """Nur Hashtags generieren"""
        prompt = f"""Generiere {count} relevante Instagram Hashtags für das Thema: {topic}

Mix aus:
- Großen Hashtags (>1M Posts)
- Mittleren Hashtags (100k-1M Posts)
- Nischen Hashtags (<100k Posts)

Antworte NUR mit den Hashtags, durch Leerzeichen getrennt."""

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
