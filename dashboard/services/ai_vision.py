"""
AI Vision Service — Analysiert Bilder mit Claude Vision.
Entscheidet: Branding anwenden ODER neues Bild mit DALL-E generieren.
"""
import base64
import json
import os
import requests
import anthropic
from pathlib import Path

def _build_analysis_prompt() -> str:
    """Baut den Vision-Prompt dynamisch aus brand_knowledge.json."""
    try:
        bk = json.loads(Path("client/brand_knowledge.json").read_text(encoding="utf-8"))
        name     = bk.get("brand_name", "Meine Marke")
        industry = bk.get("industry", "")
        tone     = ", ".join(bk.get("tone_keywords", ["professionell", "authentisch"]))
        pillars  = bk.get("content_pillars", ["Allgemeines", "Behind the Scenes"])[:4]
    except Exception:
        name, industry, tone = "Meine Marke", "", "professionell, authentisch"
        pillars = ["Allgemeines", "Behind the Scenes"]

    brand_line   = f"{name}" + (f" ({industry})" if industry else "")
    pillars_json = json.dumps(pillars[:2], ensure_ascii=False)

    return f"""Analysiere dieses Bild für den Social-Media-Einsatz bei {brand_line}.
Ton: {tone}.

Antworte NUR mit diesem JSON (kein Text drumherum):
{{
  "description": "Was ist auf dem Bild?",
  "mood": "Grundstimmung des Bildes (z.B. energetisch, professionell, casual)",
  "brand_fit_score": 7,
  "suggested_content_pillars": {pillars_json},
  "decision": "brand_overlay",
  "dall_e_prompt": "",
  "suggested_caption_topics": ["Thema 1", "Thema 2", "Thema 3"]
}}

decision = "brand_overlay" wenn das Bild gut zum Brand passt (Score >= 5).
decision = "generate_new" wenn das Bild nicht passt (Score < 5) — dann fülle dall_e_prompt aus.
dall_e_prompt: Englischer Prompt für DALL-E 3, professioneller authentischer Stil passend zum Brand."""


class AIVisionService:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key, timeout=90.0)
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def analyze_image(self, image_path: Path) -> dict:
        """Analysiert ein Bild mit Claude Vision und gibt strukturierte Analyse zurück."""
        ext = image_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            media_type = "image/jpeg"
        elif ext == ".png":
            media_type = "image/png"
        elif ext == ".webp":
            media_type = "image/webp"
        else:
            # Für Videos: kein Vision-Support → Fallback
            try:
                bk = json.loads(Path("client/brand_knowledge.json").read_text(encoding="utf-8"))
                pillars = bk.get("content_pillars", ["Allgemeines", "Behind the Scenes"])[:2]
                name    = bk.get("brand_name", "")
            except Exception:
                pillars, name = ["Allgemeines", "Behind the Scenes"], ""
            return {
                "description": "Video-Datei — automatisches Branding wird angewendet.",
                "mood": "professional",
                "brand_fit_score": 6,
                "suggested_content_pillars": pillars,
                "decision": "brand_overlay",
                "dall_e_prompt": "",
                "suggested_caption_topics": [
                    f"Behind the Scenes{' bei ' + name if name else ''}",
                    "Ein Tag im Team",
                    "Das Team stellt sich vor",
                ],
            }

        image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": _build_analysis_prompt()},
                ],
            }],
        )

        raw = message.content[0].text.strip()
        # JSON aus der Antwort extrahieren
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger(__name__).error(f"ai_vision: JSON-Parse fehlgeschlagen: {e}\nRaw: {raw[:200]}")
            raise ValueError(f"Claude hat kein gültiges JSON geliefert: {e}") from e

    def generate_dall_e_image(self, prompt: str) -> bytes:
        """Generiert ein Bild mit DALL-E 3. Gibt rohe Bild-Bytes zurück."""
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY nicht konfiguriert — DALL-E nicht verfügbar.")

        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "standard",
                "response_format": "url",
            },
            timeout=60,
        )
        resp.raise_for_status()
        image_url = resp.json()["data"][0]["url"]
        return requests.get(image_url, timeout=30).content
