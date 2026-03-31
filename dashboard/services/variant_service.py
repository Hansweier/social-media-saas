"""
Variant Service — Generiert 3 Varianten pro Post-Slot.

Varianten-Typen:
  A (empfohlen): Standard-Winkel, höchste Brand-Fitness
  B (alternativ): Anderer Blickwinkel auf gleiches Thema
  C (frisch):     Komplett anderes Thema aus der Rotation
"""
import json
import uuid
import logging
import threading
from datetime import datetime
from pathlib import Path

import anthropic

log = logging.getLogger(__name__)

SETTINGS_FILE = Path("client/bot_settings.json")
_settings_lock = threading.Lock()

VALID_DAYS      = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
VALID_PLATFORMS = {"instagram", "facebook", "linkedin", "twitter", "tiktok"}

DEFAULT_PLATFORM_SCHEDULES = {
    "instagram": {"days": ["MON", "WED", "FRI", "SUN"], "times": ["10:00", "18:00"]},
    "facebook":  {"days": ["TUE", "THU", "SAT"],        "times": ["10:00", "17:00"]},
    "linkedin":  {"days": ["MON", "WED", "FRI"],        "times": ["09:00", "12:00"]},
    "twitter":   {"days": ["MON", "TUE", "WED", "THU", "FRI"], "times": ["08:00", "12:00"]},
    "tiktok":    {"days": ["MON", "THU", "SAT"],        "times": ["15:00", "20:00"]},
}

# Template-Typen mit Beschreibungen für Claude
TEMPLATE_TYPES = {
    "A": {
        "label": "Empfohlen",
        "instruction": "Erstelle einen normalen, markenkonformen Post für diese Plattform. Optimiert für Engagement.",
    },
    "B": {
        "label": "Anderer Winkel",
        "instruction": "Behandle dasselbe Thema, aber aus einem anderen Blickwinkel: z.B. als persönliche Geschichte, als Frage an die Community, als Überraschungsaussage oder als Behind-the-Scenes-Einblick.",
    },
    "C": {
        "label": "Neues Thema",
        "instruction": "Ignoriere das vorgeschlagene Thema vollständig. Wähle ein völlig anderes, relevantes Thema für diese Plattform und Marke. Überrasche und abwechsle.",
    },
}


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"mode": "copilot"}


def _save_settings(data: dict):
    with _settings_lock:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_mode() -> str:
    return _load_settings().get("mode", "copilot")


def set_mode(mode: str):
    with _settings_lock:
        s = _load_settings()
        s["mode"] = mode
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Platform pause / resume ───────────────────────────────────────────────────

def get_paused_platforms() -> list:
    """Returns list of currently paused platform names."""
    return _load_settings().get("paused_platforms", [])


def set_platform_paused(platform: str, paused: bool):
    """Pause or resume a single platform without touching its token."""
    with _settings_lock:
        s = _load_settings()
        paused_set = set(s.get("paused_platforms", []))
        if paused:
            paused_set.add(platform)
        else:
            paused_set.discard(platform)
        s["paused_platforms"] = sorted(paused_set)
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Per-platform schedules ────────────────────────────────────────────────────

def get_generation_config() -> dict:
    """Gibt Generierungsmodus-Einstellungen zurück."""
    s = _load_settings()
    return {
        "mode":         s.get("generation_mode", "weekly"),  # "weekly" | "jit"
        "hours_before": int(s.get("jit_hours_before", 4)),
    }


def set_generation_config(mode: str, hours_before: int):
    """Speichert Generierungsmodus."""
    if mode not in ("weekly", "jit"):
        mode = "weekly"
    with _settings_lock:
        s = _load_settings()
        s["generation_mode"]   = mode
        s["jit_hours_before"]  = max(1, min(48, int(hours_before)))
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def get_platform_schedules() -> dict:
    """Returns per-platform schedule dict, falling back to defaults."""
    return _load_settings().get("platform_schedules", DEFAULT_PLATFORM_SCHEDULES)


def set_platform_schedule(platform: str, days: list, times: list):
    """Update posting schedule for one platform."""
    with _settings_lock:
        s = _load_settings()
        if "platform_schedules" not in s:
            s["platform_schedules"] = {k: dict(v) for k, v in DEFAULT_PLATFORM_SCHEDULES.items()}
        s["platform_schedules"][platform] = {
            "days":  [d.upper() for d in days  if d.upper() in VALID_DAYS],
            "times": [t for t in times if len(t) == 5 and ":" in t],
        }
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


class VariantService:
    def __init__(self, api_key: str):
        self.client  = anthropic.Anthropic(api_key=api_key)
        self.api_key = api_key

    def generate_variants(self, platform: str, topic: str, count: int = 3) -> list:
        """
        Generiert `count` Varianten für einen Post-Slot.
        Gibt Liste von Variant-Dicts zurück.
        """
        from bot.poster import Poster
        from bot.config import load_config

        variants = []
        types = ["A", "B", "C"][:count]

        for vtype in types:
            tmpl = TEMPLATE_TYPES[vtype]
            try:
                content = self._generate_with_instruction(platform, topic, tmpl["instruction"])
                score   = self._score_variant(content, platform)
                variants.append({
                    "variant_id":     str(uuid.uuid4())[:8],
                    "type":           vtype,
                    "label":          tmpl["label"],
                    "content":        content,
                    "topic":          topic if vtype != "C" else "(anderes Thema)",
                    "ai_score":       round(score, 2),
                    "generated_at":   datetime.now().isoformat(),
                    "selected":       False,
                })
                log.info(f"[Variants] {platform} Variante {vtype}: Score {score:.2f}")
            except Exception as e:
                log.error(f"[Variants] Fehler bei Variante {vtype}: {e}")

        # Beste Variante vorauswählen
        if variants:
            best = max(variants, key=lambda v: v["ai_score"])
            best["selected"] = True

        return variants

    def _generate_with_instruction(self, platform: str, topic: str, instruction: str) -> str:
        """Generiert Content mit spezifischer Template-Anweisung."""
        from brand.foerderkraft_brand import get_brand_context
        brand_ctx = get_brand_context(platform)

        platform_guides = {
            "instagram": "Max 2200 Zeichen. Emotional, visuell, Emojis willkommen. 5-10 Hashtags am Ende.",
            "facebook":  "Max 500 Zeichen. Warm, gemeinschaftlich, klarer Call-to-Action.",
            "linkedin":  "Max 1300 Zeichen. Professionell, Mehrwert-orientiert, keine übertriebenen Emojis.",
            "twitter":   "Max 280 Zeichen. Direkt, provokant oder inspirierend. 1-2 Hashtags.",
            "tiktok":    "Max 150 Zeichen. Trendy, POV-Format, Energie.",
        }

        # Build learning context from intelligence engine
        learning_block = ""
        try:
            from dashboard.services.learning_service import generate_intelligence_context
            ctx = generate_intelligence_context(platform)
            if ctx:
                learning_block = "\n\n" + ctx
        except Exception:
            pass

        prompt = f"""{brand_ctx}{learning_block}

Plattform: {platform.upper()} — {platform_guides.get(platform, '')}
Thema: {topic}

Aufgabe: {instruction}

Schreibe NUR den fertigen Post-Text. Keine Erklärungen, kein Präambel."""

        msg = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        content = msg.content[0].text.strip()
        if platform == "twitter":
            content = self._trim_twitter(content)
        return content

    @staticmethod
    def _trim_twitter(text: str, limit: int = 280) -> str:
        """Trim Twitter/X post to 280 chars, stripping hashtags first if needed."""
        if len(text) <= limit:
            return text
        # Try stripping hashtags from end
        lines = text.split("\n")
        body_lines = [l for l in lines if not l.strip().startswith("#")]
        trimmed = "\n".join(body_lines).strip()
        if len(trimmed) <= limit:
            return trimmed
        # Hard truncate at word boundary
        truncated = trimmed[:limit - 1].rsplit(" ", 1)[0]
        return truncated + "…"

    def _score_variant(self, content: str, platform: str) -> float:
        """
        Bewertet eine Variante (0.0–1.0) basierend auf Brand-Fitness.
        Schnelle Heuristik ohne zusätzlichen API-Call.
        """
        score = 0.7  # Basis
        # Längen-Check
        limits = {"instagram": 2200, "facebook": 500, "linkedin": 1300, "twitter": 280, "tiktok": 150}
        limit  = limits.get(platform, 1000)
        if len(content) > limit * 1.1:
            score -= 0.15
        # Brand-Keywords
        brand_words = ["förderkraft", "drk", "rotes kreuz", "haustür", "außendienst", "spende", "förder"]
        matches = sum(1 for w in brand_words if w in content.lower())
        score += min(matches * 0.04, 0.2)
        # Hashtag-Präsenz bei Instagram/TikTok
        if platform in ("instagram", "tiktok") and "#" in content:
            score += 0.05
        return min(max(score, 0.0), 1.0)

    def improve_variant(self, platform: str, current_content: str, instruction: str) -> str:
        """Verbessert einen bestehenden Post-Text nach Anweisung."""
        from brand.foerderkraft_brand import get_brand_context
        brand_ctx = get_brand_context(platform)

        platform_guides = {
            "instagram": "Max 2200 Zeichen. Emotional, visuell, Emojis willkommen. 5-10 Hashtags am Ende.",
            "facebook":  "Max 500 Zeichen. Warm, gemeinschaftlich, klarer Call-to-Action.",
            "linkedin":  "Max 1300 Zeichen. Professionell, Mehrwert-orientiert, keine übertriebenen Emojis.",
            "twitter":   "Max 280 Zeichen. Direkt, provokant oder inspirierend. 1-2 Hashtags.",
            "tiktok":    "Max 150 Zeichen. Trendy, POV-Format, Energie.",
        }

        # Learning context
        learning_block = ""
        try:
            from dashboard.services.learning_service import generate_intelligence_context
            ctx = generate_intelligence_context(platform)
            if ctx:
                learning_block = "\n\n" + ctx
        except Exception:
            pass

        prompt = f"""{brand_ctx}{learning_block}
Plattform: {platform.upper()} — {platform_guides.get(platform, '')}

Bestehender Post:
\"\"\"
{current_content}
\"\"\"

Aufgabe: {instruction}

Schreibe NUR den verbesserten Post-Text. Behalte die Kernaussage, optimiere Stil und Wirkung. Keine Erklärungen."""

        msg = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        result = msg.content[0].text.strip()
        if platform == "twitter":
            result = self._trim_twitter(result)
        return result

    def select_variant(self, post: dict, variant_id: str) -> dict:
        return VariantService.select_variant_static(post, variant_id)

    @staticmethod
    def select_variant_static(post: dict, variant_id: str) -> dict:
        """Wählt eine Variante aus und aktualisiert den Post."""
        found = False
        for v in post.get("variants", []):
            v["selected"] = (v["variant_id"] == variant_id)
            if v["selected"]:
                post["content"]             = v["content"]
                post["selected_variant_id"] = variant_id
                found = True
        if not found:
            return None
        post["approval_status"] = "freigegeben"
        post["approved_at"]     = datetime.now().isoformat()
        post["status"]          = "freigegeben"
        return post
