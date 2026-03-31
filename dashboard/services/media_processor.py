"""
Media Processor — Orchestriert die KI-Bildverarbeitungs-Pipeline.

1. Claude Vision analysiert das Bild
2. Entscheidung: Branding anwenden ODER DALL-E generieren
3. Ergebnis landet in client/media/processed/ + Queue
"""
import json
import logging
from pathlib import Path
from datetime import datetime

from dashboard.services.ai_vision import AIVisionService
from dashboard.services.image_branding import ImageBrander

MEDIA_DIR     = Path("client/media")
PROCESSED_DIR = Path("client/media/processed")
QUEUE_DIR     = Path("client/media/queue")
log = logging.getLogger(__name__)


class MediaProcessor:
    def __init__(self, config: dict):
        self.vision  = AIVisionService(config["claude"]["api_key"])
        self.brander = ImageBrander()

    def process(self, media_id: str, platform: str = "instagram") -> dict:
        """
        Vollständige Pipeline für ein hochgeladenes Bild.
        Gibt das Queue-Manifest zurück.
        """
        original  = MEDIA_DIR / media_id
        sidecar   = original.with_suffix(".json")
        processed = PROCESSED_DIR / media_id

        if not original.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {original}")

        # ── Sidecar aktualisieren ─────────────────────────────────────────
        def _update_sidecar(updates: dict):
            meta = {}
            if sidecar.exists():
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                except Exception:
                    pass
            meta.update(updates)
            sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        # ── 1. Analyse ────────────────────────────────────────────────────
        _update_sidecar({"status": "analyzing"})
        log.info(f"[MediaProcessor] Analysiere: {media_id}")

        try:
            analysis = self.vision.analyze_image(original)
        except Exception as e:
            log.error(f"[MediaProcessor] Vision-Fehler: {e}")
            _update_sidecar({"status": "fehler", "error": str(e)})
            raise

        _update_sidecar({"ai_analysis": analysis})
        log.info(f"[MediaProcessor] Entscheidung: {analysis.get('decision')} "
                 f"(Score {analysis.get('brand_fit_score')})")

        # ── 2. Bild verarbeiten ───────────────────────────────────────────
        source = "unknown"
        try:
            if analysis.get("decision") == "generate_new" and analysis.get("dall_e_prompt"):
                try:
                    log.info("[MediaProcessor] Generiere DALL-E Bild...")
                    img_bytes = self.vision.generate_dall_e_image(analysis["dall_e_prompt"])
                    processed.parent.mkdir(parents=True, exist_ok=True)
                    processed.with_suffix(".jpg").write_bytes(img_bytes)
                    processed = processed.with_suffix(".jpg")
                    source = "dall_e_generated"
                except Exception as e:
                    log.warning(f"[MediaProcessor] DALL-E fehlgeschlagen, Fallback auf Branding: {e}")
                    processed = self.brander.apply_branding(
                        original, processed.with_suffix(".jpg"), {"platform": platform}
                    )
                    source = "original_branded_fallback"
            else:
                log.info("[MediaProcessor] Wende Branding an...")
                processed = self.brander.apply_branding(
                    original, processed.with_suffix(".jpg"), {"platform": platform}
                )
                source = "original_branded"

        except Exception as e:
            log.error(f"[MediaProcessor] Bildverarbeitung fehlgeschlagen: {e}")
            _update_sidecar({"status": "fehler", "error": str(e)})
            raise

        # ── 3. Queue-Manifest erstellen ───────────────────────────────────
        manifest = {
            "media_id":          media_id,
            "original_path":     str(original),
            "processed_path":    str(processed),
            "platform":          platform,
            "ai_analysis":       analysis,
            "suggested_topics":  analysis.get("suggested_caption_topics", []),
            "source":            source,
            "queue_status":      "ready",
            "created_at":        datetime.now().isoformat(),
        }

        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = QUEUE_DIR / f"{media_id}.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        _update_sidecar({"status": "processed", "queue_status": "ready", "processed_path": str(processed)})
        log.info(f"[MediaProcessor] Fertig: {media_id} → {source}")
        return manifest
