"""
Brand Extractor — Liest PDFs mit Claude und extrahiert Markeninfos.
Speichert Ergebnisse in client/brand_knowledge.json.
"""
import base64
import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic

BRAND_FILE = Path("client/brand_knowledge.json")
log = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Du bist ein Brand-Stratege. Lies dieses Dokument und extrahiere alle relevanten Markeninformationen.

Antworte NUR mit diesem JSON (kein Text drumherum):
{
  "brand_name": "Firmenname",
  "slogan": "Slogan falls vorhanden",
  "industry": "Branche",
  "mission": "Unternehmensmission",
  "target_audience": ["Zielgruppe 1", "Zielgruppe 2"],
  "values": ["Wert 1", "Wert 2", "Wert 3"],
  "usp": ["Alleinstellungsmerkmal 1", "Alleinstellungsmerkmal 2"],
  "tone_keywords": ["professionell", "menschlich", "direkt"],
  "colors": ["#hex1", "#hex2"],
  "avoid": ["Was vermieden werden soll"],
  "key_messages": ["Kernbotschaft 1", "Kernbotschaft 2"],
  "platforms_focus": ["instagram", "linkedin"],
  "example_phrases": ["Beispielformulierung 1"]
}

Wenn eine Information nicht im Dokument vorhanden ist, setze null oder leeres Array."""


class BrandExtractor:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract_from_pdf(self, pdf_path: Path) -> dict:
        """
        Liest eine PDF-Datei und extrahiert Markeninformationen via Claude.
        Gibt strukturiertes Brand-Dict zurück.
        """
        pdf_bytes = pdf_path.read_bytes()
        pdf_b64   = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        log.info(f"[BrandExtractor] Analysiere PDF: {pdf_path.name} ({len(pdf_bytes)//1024}KB)")

        msg = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": _EXTRACT_PROMPT},
                ],
            }],
        )

        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger(__name__).error(f"brand_extractor: JSON-Parse fehlgeschlagen: {e}\nRaw: {raw[:200]}")
            raise ValueError(f"Claude hat kein gültiges JSON geliefert: {e}") from e

    def save_brand_knowledge(self, facts: dict, source_filename: str = "") -> bool:
        """Speichert extrahierte Brand-Infos in client/brand_knowledge.json."""
        facts["source_pdf"]        = source_filename
        facts["extracted_at"]      = datetime.now().isoformat()
        facts["confirmed_by_user"] = False
        facts["confirmed_at"]      = None

        BRAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRAND_FILE.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"[BrandExtractor] Brand-Wissen gespeichert: {BRAND_FILE}")
        return True

    def confirm_brand_knowledge(self, updated_facts: dict) -> bool:
        """Bestätigt die extrahierten Daten (nach User-Review)."""
        if BRAND_FILE.exists():
            existing = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
            existing.update(updated_facts)
            existing["confirmed_by_user"] = True
            existing["confirmed_at"]      = datetime.now().isoformat()
            BRAND_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        return False

    @staticmethod
    def load_brand_knowledge() -> dict:
        """Lädt gespeicherte Brand-Infos. Fallback auf foerderkraft_brand.py."""
        if BRAND_FILE.exists():
            try:
                data = json.loads(BRAND_FILE.read_text(encoding="utf-8"))
                if data.get("confirmed_by_user"):
                    return data
            except Exception:
                pass
        # Fallback
        from brand.foerderkraft_brand import BRAND
        return {
            "brand_name":    BRAND["name"],
            "mission":       BRAND["core_service"],
            "values":        BRAND["values"],
            "tone_keywords": ["professionell", "menschlich", "direkt"],
        }
