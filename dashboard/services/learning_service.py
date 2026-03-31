"""
Learning Engine — Stille KI-Intelligenz die mit jeder Interaktion besser wird.

Drei Lernquellen:
  1. Nutzerverhalten  — welche Varianten werden gewählt, warum werden Posts abgelehnt,
                        werden Posts vor Freigabe editiert
  2. Social-Performance — Engagement-Daten von den Plattformen (Likes, Reach, Comments)
  3. Meta-Analyse      — Claude analysiert seine eigenen freigegebenen Posts periodisch
                        und extrahiert präzise Stil-Regeln für die Marke

Das Ergebnis ist ein wachsender Intelligence-Context der in jeden Claude-Prompt
injiziert wird und die Generierungs-Qualität kontinuierlich verbessert.
"""
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

LEARNING_FILE = Path("client/learning_profile.json")
PLATFORMS     = {"instagram", "facebook", "linkedin", "twitter", "tiktok"}

# Meta-Analyse läuft frühestens alle 20 Freigaben pro Plattform
META_ANALYSIS_INTERVAL = 20

REASON_STYLE_HINTS = {
    "ton":       "Ton/Stil anpassen",
    "laenge":    "Länge optimieren",
    "qualitaet": "Generische Formulierungen vermeiden",
    "inhalt":    "Marken-Relevanz verbessern",
    "thema":     "Themenauswahl verbessern",
}


# ── Datenmodell ───────────────────────────────────────────────────────────────

def _empty_platform() -> dict:
    return {
        "approved_topics":   [],
        "approved_styles":   [],
        "rejected_topics":   [],
        "rejected_styles":   [],
        "rejection_reasons": [],
        "approval_history":  [],
        "performance_data":  [],   # {post_id, metrics, excerpt, timestamp}
        "learned_patterns":  {},   # statistische Muster (wird automatisch befüllt)
        "style_analysis":    "",   # Claude Meta-Analyse Ergebnis
        "style_analysis_at": "",   # Zeitstempel der letzten Meta-Analyse
        "interactions_since_meta": 0,  # Zähler für nächste Meta-Analyse
    }


def _empty_profile() -> dict:
    return {
        "version":    2,
        "updated_at": datetime.now().isoformat(),
        "per_platform": {p: _empty_platform() for p in PLATFORMS},
        "global": {
            "always_avoid":  [],
            "always_prefer": [],
        },
    }


def _load() -> dict:
    if LEARNING_FILE.exists():
        try:
            p = json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
            # Migriere alte Profile (version 1) auf version 2
            if p.get("version", 1) < 2:
                for plat in PLATFORMS:
                    pp = p.setdefault("per_platform", {}).setdefault(plat, {})
                    for key, default in _empty_platform().items():
                        pp.setdefault(key, default)
                p["version"] = 2
            return p
        except Exception:
            log.warning("[Learning] Korrupte learning_profile.json — reset.")
    return _empty_profile()


def _save(profile: dict):
    profile["updated_at"] = datetime.now().isoformat()
    LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEARNING_FILE.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Muster-Analyse ────────────────────────────────────────────────────────────

def _analyze_patterns(plat_data: dict) -> dict:
    """
    Extrahiert statistische Muster aus Freigabe- und Ablehungs-History.
    Wird nach jeder Interaktion aktualisiert.
    """
    history    = plat_data.get("approval_history", [])
    rejections = plat_data.get("rejection_reasons", [])
    total      = len(history) + len(rejections)

    patterns = {"total_interactions": total}
    if total == 0:
        return patterns

    # Freigaberate
    patterns["approval_rate"] = round(len(history) / total, 3)

    # Welcher Varianten-Typ wird bevorzugt?
    type_wins = {}
    for h in history:
        vt = h.get("variant_type", "A")
        type_wins[vt] = type_wins.get(vt, 0) + 1
    if type_wins:
        patterns["variant_wins"]      = type_wins
        patterns["preferred_variant"] = max(type_wins, key=type_wins.get)

    # Durchschnittlicher AI-Score freigegebener Posts
    scores = [h.get("ai_score", 0.0) for h in history if h.get("ai_score")]
    if scores:
        patterns["avg_approved_score"] = round(sum(scores) / len(scores), 3)

    # Häufigste Ablehnungsgründe
    cat_counts = {}
    for r in rejections:
        cat = r.get("reason_category", "sonstige")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    if cat_counts:
        patterns["top_rejection_cats"] = sorted(
            cat_counts.items(), key=lambda x: -x[1]
        )[:4]

    # Top-Performance Posts (aus Social-Daten)
    perf = plat_data.get("performance_data", [])
    if perf:
        top = sorted(perf, key=lambda x: x.get("engagement_rate", 0), reverse=True)[:3]
        patterns["top_performing_topics"] = [p.get("topic", "") for p in top if p.get("topic")]

    return patterns


# ── Signale aufzeichnen ───────────────────────────────────────────────────────

def record_approval(
    post_id: str,
    platform: str,
    topic: str,
    variant_type: str = "A",
    ai_score: float = 0.0,
    content: str = "",
    note: str = "",
) -> None:
    """Speichert Freigabe und aktualisiert Lernmuster."""
    if platform not in PLATFORMS:
        return
    try:
        profile = _load()
        plat    = profile["per_platform"].setdefault(platform, _empty_platform())

        entry = {
            "post_id":      post_id,
            "topic":        topic,
            "variant_type": variant_type,
            "ai_score":     round(ai_score, 3),
            "content_len":  len(content),
            "excerpt":      content[:120] if content else "",
            "timestamp":    datetime.now().isoformat(),
        }
        if note:
            entry["approval_note"] = note[:300]
            # Nutzer-Note als positives Stil-Signal speichern
            if note not in plat.get("approved_styles", []):
                plat.setdefault("approved_styles", []).append(f"Nutzer-Notiz: {note[:150]}")
            plat["approved_styles"] = plat["approved_styles"][-15:]
        plat["approval_history"].append(entry)
        plat["approval_history"] = plat["approval_history"][-200:]

        # Thema als bevorzugt markieren
        if topic and topic not in plat["approved_topics"]:
            plat["approved_topics"].append(topic)
        plat["approved_topics"] = plat["approved_topics"][-30:]

        # Thema aus Vermeidungsliste entfernen wenn jetzt freigegeben
        if topic in plat["rejected_topics"]:
            plat["rejected_topics"].remove(topic)

        # Statistische Muster aktualisieren
        plat["learned_patterns"] = _analyze_patterns(plat)

        # Meta-Analyse triggern wenn genug neue Daten
        plat["interactions_since_meta"] = plat.get("interactions_since_meta", 0) + 1

        _save(profile)
        log.info(f"[Learning] Freigabe: {platform}/{topic} Typ={variant_type} Score={ai_score:.2f}")

        # Meta-Analyse im Hintergrund starten wenn Interval erreicht
        if (plat["interactions_since_meta"] >= META_ANALYSIS_INTERVAL
                and len(plat["approval_history"]) >= 5):
            threading.Thread(
                target=_trigger_meta_analysis, args=(platform,), daemon=True
            ).start()

    except Exception as e:
        log.error(f"[Learning] Fehler bei Freigabe-Speicherung: {e}")


def record_rejection(
    post_id: str,
    platform: str,
    topic: str,
    variant_type: str = "A",
    reason_category: str = "sonstige",
    reason_text: str = "",
) -> None:
    """Speichert Ablehnung und aktualisiert Lernmuster."""
    if platform not in PLATFORMS:
        return
    try:
        profile = _load()
        plat    = profile["per_platform"].setdefault(platform, _empty_platform())

        plat["rejection_reasons"].append({
            "post_id":         post_id,
            "reason_category": reason_category,
            "reason_text":     reason_text[:300],
            "topic":           topic,
            "variant_type":    variant_type,
            "timestamp":       datetime.now().isoformat(),
        })
        plat["rejection_reasons"] = plat["rejection_reasons"][-100:]

        # Thema nach 2× Ablehnung auf Vermeiden-Liste
        if topic:
            topic_count = sum(
                1 for r in plat["rejection_reasons"] if r.get("topic") == topic
            )
            if topic_count >= 2 and topic not in plat["rejected_topics"]:
                plat["rejected_topics"].append(topic)
        plat["rejected_topics"] = plat["rejected_topics"][-30:]

        # Stil-Hinweis aus Ablehnungsgrund extrahieren
        style_hint = None
        if reason_text and len(reason_text) > 5:
            style_hint = reason_text[:100]
        elif reason_category in REASON_STYLE_HINTS:
            style_hint = REASON_STYLE_HINTS[reason_category]
        if style_hint and style_hint not in plat["rejected_styles"]:
            plat["rejected_styles"].append(style_hint)
        plat["rejected_styles"] = plat["rejected_styles"][-15:]

        # Muster aktualisieren
        plat["learned_patterns"] = _analyze_patterns(plat)
        plat["interactions_since_meta"] = plat.get("interactions_since_meta", 0) + 1

        _save(profile)
        log.info(f"[Learning] Ablehnung: {platform}/{topic} Grund={reason_category}")

    except Exception as e:
        log.error(f"[Learning] Fehler bei Ablehungs-Speicherung: {e}")


def record_rating(
    post_id: str,
    platform: str,
    topic: str,
    variant_type: str = "A",
    rating: str = "",
    content: str = "",
) -> None:
    """
    Speichert eine Nutzer-Bewertung (❤️/👍/✏️) für eine Variante.
    Positive Ratings fließen als Stil-Signale in den Lernkontext ein.
    """
    if platform not in PLATFORMS or rating not in ("love", "good", "meh"):
        return
    try:
        profile = _load()
        plat    = profile["per_platform"].setdefault(platform, _empty_platform())

        # "love" und "good" sind positive Signale — wie eine weiche Freigabe
        if rating in ("love", "good") and content:
            hint = f"{'❤️ Perfekt' if rating == 'love' else '👍 Gut'}: {content[:100]}"
            plat.setdefault("approved_styles", []).append(hint)
            plat["approved_styles"] = plat["approved_styles"][-15:]

        # "meh" (Fast gut) signalisiert: Thema OK, Stil verbesserungswürdig
        if rating == "meh" and variant_type not in plat.get("rejected_styles", []):
            plat.setdefault("rejected_styles", []).append(
                f"Stil fast gut aber verbesserungswürdig (Typ {variant_type})"
            )
            plat["rejected_styles"] = plat["rejected_styles"][-15:]

        plat["learned_patterns"] = _analyze_patterns(plat)
        _save(profile)
        log.info(f"[Learning] Rating: {platform}/{topic} Typ={variant_type} Rating={rating}")
    except Exception as e:
        log.error(f"[Learning] Fehler bei Rating-Speicherung: {e}")


def record_performance(
    post_id: str,
    platform: str,
    topic: str,
    content: str,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    reach: int = 0,
    saves: int = 0,
) -> None:
    """
    Speichert Social-Media Performance-Daten eines Posts.
    Wird vom Analytics-Modul aufgerufen nachdem Engagement-Daten vorliegen.
    Hochperformante Posts fließen als Stil-Vorbilder in den Lernkontext ein.
    """
    if platform not in PLATFORMS:
        return
    try:
        engagement_rate = round(
            (likes + comments + shares + saves) / max(reach, 1) * 100, 3
        )
        profile = _load()
        plat    = profile["per_platform"].setdefault(platform, _empty_platform())

        # Bestehenden Eintrag updaten wenn vorhanden
        existing = next(
            (p for p in plat["performance_data"] if p.get("post_id") == post_id), None
        )
        entry = {
            "post_id":        post_id,
            "topic":          topic,
            "excerpt":        content[:150] if content else "",
            "likes":          likes,
            "comments":       comments,
            "shares":         shares,
            "reach":          reach,
            "saves":          saves,
            "engagement_rate": engagement_rate,
            "timestamp":      datetime.now().isoformat(),
        }
        if existing:
            existing.update(entry)
        else:
            plat["performance_data"].append(entry)
        plat["performance_data"] = plat["performance_data"][-100:]

        # Hochperformante Posts → als Style-Vorbilder kennzeichnen
        avg_rate = (
            sum(p.get("engagement_rate", 0) for p in plat["performance_data"])
            / len(plat["performance_data"])
            if plat["performance_data"] else 0
        )
        if engagement_rate > avg_rate * 1.5 and content:
            # Inhalt als bevorzugt markieren (kurzer Stil-Hinweis)
            hint = f"Hohe Performance ({engagement_rate:.1f}% Engagement): {content[:80]}"
            if hint not in plat.get("approved_styles", []):
                plat.setdefault("approved_styles", []).append(hint)
            plat["approved_styles"] = plat["approved_styles"][-10:]

        plat["learned_patterns"] = _analyze_patterns(plat)
        _save(profile)
        log.info(
            f"[Learning] Performance: {platform}/{topic} "
            f"Engagement={engagement_rate:.1f}% Reach={reach}"
        )
    except Exception as e:
        log.error(f"[Learning] Fehler bei Performance-Speicherung: {e}")


# ── Meta-Analyse: Claude lernt von Claude ────────────────────────────────────

def _trigger_meta_analysis(platform: str):
    """
    Periodischer Hintergrundprozess: Claude analysiert die letzten freigegebenen
    Posts und destilliert präzise Stil-Regeln für diese Marke + Plattform.
    Ergebnis wird als 'style_analysis' gespeichert und in alle Prompts injiziert.
    """
    try:
        from bot.config import load_config
        config  = load_config()
        api_key = config.get("claude", {}).get("api_key", "")
        if not api_key or "dein" in api_key:
            return

        profile = _load()
        plat    = profile["per_platform"].get(platform, _empty_platform())
        history = plat.get("approval_history", [])

        # Nur Posts mit gespeichertem Excerpt analysieren
        excerpts = [
            h["excerpt"] for h in history[-25:]
            if h.get("excerpt") and len(h["excerpt"]) > 30
        ]
        if len(excerpts) < 5:
            return

        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        posts_block = "\n\n".join(
            f"Post {i+1}:\n{e}" for i, e in enumerate(excerpts[-15:])
        )

        prompt = f"""Du analysierst freigegebene Social-Media Posts für {platform.upper()}.
Diese Posts wurden alle vom Kunden genehmigt — sie repräsentieren genau den gewünschten Stil.

{posts_block}

Analysiere diese Posts sorgfältig und schreibe EXAKT 4 spezifische Stil-Regeln,
die beschreiben was diese Marke auf {platform.upper()} auszeichnet.

Format (gib nur die 4 Regeln zurück, keine Einleitung):
• [Regel 1: Ton/Sprache]
• [Regel 2: Struktur/Aufbau]
• [Regel 3: Länge/Format]
• [Regel 4: Was vermieden wird]

Sei sehr konkret und handlungsleitend — nicht generisch."""

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku reicht für Meta-Analyse
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = msg.content[0].text.strip()

        profile = _load()  # reload to avoid overwrite race
        pp = profile["per_platform"].setdefault(platform, _empty_platform())
        pp["style_analysis"]    = analysis
        pp["style_analysis_at"] = datetime.now().isoformat()
        pp["interactions_since_meta"] = 0
        _save(profile)

        log.info(f"[Learning] Meta-Analyse für {platform} abgeschlossen.")

    except Exception as e:
        log.error(f"[Learning] Meta-Analyse Fehler ({platform}): {e}")


# ── Intelligence Context für Claude-Prompts ──────────────────────────────────

def generate_intelligence_context(platform: str) -> str:
    """
    Generiert den gesamten Lern-Kontext für Claude-Prompts.
    Kombiniert statistische Muster, Stil-Analyse und Performance-Daten.
    Wächst in Präzision mit jeder Interaktion.
    """
    try:
        profile  = _load()
        plat     = profile["per_platform"].get(platform, _empty_platform())
        patterns = plat.get("learned_patterns", {})
        total    = patterns.get("total_interactions", 0)

        if total < 3:
            # Noch zu wenig Daten — einfache Liste reicht
            return _simple_hints(plat, profile)

        lines = [f"=== Lernkontext ({total} analysierte Posts) ==="]

        # Freigaberate
        rate = round(patterns.get("approval_rate", 0) * 100)
        lines.append(f"Aktuelle Freigaberate: {rate}%")

        # Bevorzugter Varianten-Typ
        pref = patterns.get("preferred_variant")
        wins = patterns.get("variant_wins", {})
        if pref and sum(wins.values()) >= 5:
            type_labels = {
                "A": "Standard-Format",
                "B": "persönliche Geschichte / alternativer Winkel",
                "C": "überraschendes neues Thema",
            }
            pct = round(wins.get(pref, 0) / sum(wins.values()) * 100)
            lines.append(
                f"Bevorzugter Stil: Variante {pref} "
                f"({type_labels.get(pref, pref)}, {pct}% der Freigaben)"
            )

        # Top-Ablehnungsgründe → direkte Anweisungen für Claude
        top_cats = patterns.get("top_rejection_cats", [])
        if top_cats:
            cat_instructions = {
                "ton":       "Tone anpassen — authentischer, weniger werblich",
                "laenge":    "Länge optimieren — nicht zu lang, nicht zu kurz",
                "qualitaet": "Keine generischen Phrasen — konkret und spezifisch schreiben",
                "inhalt":    "Direkte Marken-Relevanz sicherstellen",
                "thema":     "Thema zur Marke und Zielgruppe passen",
            }
            instructions = [
                cat_instructions[c] for c, _ in top_cats if c in cat_instructions
            ]
            if instructions:
                lines.append("Häufige Fehler vermeiden: " + " · ".join(instructions))

        # Bewährte Topics
        if plat.get("approved_topics"):
            lines.append("Bewährte Themen: " + ", ".join(plat["approved_topics"][-6:]))

        # Vermiedene Topics
        if plat.get("rejected_topics"):
            lines.append("Themen vermeiden: " + ", ".join(plat["rejected_topics"][-6:]))

        # Stil vermeiden
        if plat.get("rejected_styles"):
            lines.append("Stil vermeiden: " + " · ".join(plat["rejected_styles"][-4:]))

        # Top-Performance Themen (aus echten Social-Daten)
        top_topics = patterns.get("top_performing_topics", [])
        if top_topics:
            lines.append(
                "Top-Performance Themen (hohes Engagement): "
                + ", ".join(t for t in top_topics if t)
            )

        # Bevorzugte Styles (aus Performance-Daten)
        perf_styles = [
            s for s in plat.get("approved_styles", [])
            if "Hohe Performance" in s
        ]
        if perf_styles:
            lines.append(
                "Posting-Formate mit nachgewiesenem Engagement: "
                + "; ".join(s[:60] for s in perf_styles[-2:])
            )

        # Globale Präferenzen
        global_avoid  = profile.get("global", {}).get("always_avoid", [])
        global_prefer = profile.get("global", {}).get("always_prefer", [])
        if global_avoid:
            lines.append("Immer vermeiden: " + ", ".join(global_avoid))
        if global_prefer:
            lines.append("Immer bevorzugen: " + ", ".join(global_prefer))

        # Meta-Analyse Ergebnis (Claude's eigene Stil-Analyse)
        style_analysis = plat.get("style_analysis", "").strip()
        if style_analysis:
            lines.append("\nDestillierte Stil-Regeln dieser Marke (aus KI-Analyse):")
            lines.append(style_analysis)

        context = "\n".join(lines)
        log.debug(f"[Learning] Intelligence context für {platform}: {total} Datenpunkte")
        return context

    except Exception as e:
        log.error(f"[Learning] Fehler bei Context-Generierung: {e}")
        return ""


def _simple_hints(plat: dict, profile: dict) -> str:
    """Fallback für wenig Daten: einfache Hinweis-Liste."""
    parts = []
    if plat.get("approved_topics"):
        parts.append("Bewährte Themen: " + ", ".join(plat["approved_topics"][-4:]))
    if plat.get("rejected_topics"):
        parts.append("Themen vermeiden: " + ", ".join(plat["rejected_topics"][-4:]))
    if plat.get("rejected_styles"):
        parts.append("Stil vermeiden: " + "; ".join(plat["rejected_styles"][-3:]))
    global_avoid  = profile.get("global", {}).get("always_avoid", [])
    global_prefer = profile.get("global", {}).get("always_prefer", [])
    if global_avoid:
        parts.append("Immer vermeiden: " + ", ".join(global_avoid))
    if global_prefer:
        parts.append("Immer bevorzugen: " + ", ".join(global_prefer))
    return "\n".join(parts)


# ── Compat: alte get_prompt_hints() Schnittstelle ─────────────────────────────

def get_prompt_hints(platform: str) -> dict:
    """Rückwärtskompatibilität — gibt weiterhin das alte Dict zurück."""
    try:
        profile = _load()
        plat    = profile["per_platform"].get(platform, _empty_platform())
        return {
            "approved_topics": plat["approved_topics"][-6:],
            "approved_styles": plat["approved_styles"][-3:],
            "rejected_topics": plat["rejected_topics"][-6:],
            "rejected_styles": plat["rejected_styles"][-3:],
            "global_avoid":    profile["global"].get("always_avoid", []),
            "global_prefer":   profile["global"].get("always_prefer", []),
        }
    except Exception:
        return {
            "approved_topics": [], "approved_styles": [],
            "rejected_topics": [], "rejected_styles": [],
            "global_avoid": [],    "global_prefer": [],
        }


def get_profile_summary() -> dict:
    """Dashboard-Summary für das Learning Profile."""
    try:
        profile = _load()
        summary = {}
        for platform, data in profile["per_platform"].items():
            total_rejected = len(data.get("rejection_reasons", []))
            total_approved = len(data.get("approval_history", []))
            if total_rejected + total_approved == 0:
                continue
            patterns = data.get("learned_patterns", {})
            summary[platform] = {
                "approved":      total_approved,
                "rejected":      total_rejected,
                "approval_rate": round(patterns.get("approval_rate", 0) * 100),
                "avoid_topics":  data.get("rejected_topics", [])[-3:],
                "prefer_topics": data.get("approved_topics", [])[-3:],
                "has_meta":      bool(data.get("style_analysis")),
                "total_posts":   len(data.get("performance_data", [])),
            }
        return summary
    except Exception:
        return {}
