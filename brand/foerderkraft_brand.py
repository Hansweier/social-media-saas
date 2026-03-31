# ============================================================
# FÖRDERKRAFT GMBH - BRAND VOICE & IDENTITY
# ============================================================
# Zentrale Markendefinition - wird von allen Plattformen genutzt
# Hier alle Infos über den Kunden anpassen!
# ============================================================

import json
import re
from pathlib import Path

_DEFAULTS = {
    # --------------------------------------------------------
    # GRUNDLEGENDE MARKENIDENTITÄT (Fallback — wird durch brand_knowledge.json überschrieben)
    # --------------------------------------------------------
    "name": "Meine Marke",
    "slogan": "Dein Slogan hier.",
    "industry": "Branche noch nicht konfiguriert",
    "core_service": "Bitte zuerst den Onboarding-Fragebogen ausfüllen unter /fragebogen",
    "founded": "",
    "auftraggeber": "",
    "auftraggeber_mission": "",
    "target_clients": "Noch nicht konfiguriert",

    # --------------------------------------------------------
    # MARKENWERTE (werden aus brand_knowledge.json geladen)
    # --------------------------------------------------------
    "values": [
        "Qualität & Verlässlichkeit",
        "Kundenfokus",
        "Innovation",
    ],

    # --------------------------------------------------------
    # UNIQUE SELLING POINTS (werden aus brand_knowledge.json geladen)
    # --------------------------------------------------------
    "usp": [
        "Hier USPs eintragen",
    ],

    # --------------------------------------------------------
    # ZIELGRUPPEN
    # --------------------------------------------------------
    "target_audience": {
        "b2b_clients": "Unternehmen (KMU bis Konzern) die Neukundengewinnung outsourcen wollen",
        "recruits": "Ambitionierte junge Menschen die im Vertrieb Karriere machen wollen",
        "partners": "Kooperationspartner & Netzwerkpartner",
    },

    # --------------------------------------------------------
    # SCHREIBSTIL - ALLGEMEIN
    # --------------------------------------------------------
    "general_tone": {
        "personality": "Selbstbewusst, nahbar, professionell, motivierend",
        "avoid": [
            "Zu formelle Sprache (klingt steif)",
            "Übertriebene Werbesprache (klingt billig)",
            "Negative Formulierungen",
            "Zu viele Fremdwörter",
            "Passive Formulierungen",
        ],
        "always": [
            "Aktive Sprache verwenden",
            "Konkrete Zahlen & Ergebnisse nennen wenn möglich",
            "Den Leser direkt ansprechen (Du/Sie je nach Plattform)",
            "Mehrwert in den Vordergrund stellen",
            "Authentizität über Perfektion",
        ],
    },

    # --------------------------------------------------------
    # PLATTFORM-SPEZIFISCHE BRAND VOICE
    # --------------------------------------------------------
    "platform_voices": {

        "linkedin": {
            "tone": "Professionell, expert, inspirierend, B2B-fokussiert",
            "anrede": "Sie",
            "style": "Thought Leadership — Die Marke als Experte der Branche positionieren",
            "content_pillars": [
                "Vertriebstipps & Brancheninsights",
                "Erfolgsgeschichten von Kunden",
                "Recruiting & Karriere im Vertrieb",
                "Hinter die Kulissen der Agentur",
                "Markttrends im Direktvertrieb",
            ],
            "example_opening_lines": [
                "Der persönliche Erstkontakt entscheidet alles.",
                "Warum 73% unserer Kunden nach der ersten Kampagne wiederkommen.",
                "Direktvertrieb ist tot? Wir beweisen das Gegenteil.",
                "Was digitales Marketing nicht kann - aber unsere Vertriebler schon.",
            ],
            "cta_examples": [
                "Lassen Sie uns über Ihre nächste Kampagne sprechen.",
                "Verbinden Sie sich mit uns für ein kostenloses Erstgespräch.",
                "Kommentieren Sie: Was ist Ihre größte Herausforderung bei der Neukundengewinnung?",
            ],
            "hashtags_permanent": [],
        },

        "instagram": {
            "tone": "Dynamisch, modern, visuell, motivierend, authentisch",
            "anrede": "du",
            "style": "Markenaufbau durch starke Bilder und inspirierende Captions",
            "content_pillars": [
                "Team & Unternehmenskultur",
                "Motivations-Content für Vertriebler",
                "Erfolge feiern (Meilensteine, Deals, Wachstum)",
                "Behind the Scenes",
                "Recruiting & Teamwachstum",
            ],
            "example_opening_lines": [
                "Jeden Tag eine neue Chance. Jeden Klingel ein neuer Anfang.",
                "Das ist kein Job. Das ist eine Einstellung.",
                "Während andere tippen, klingeln wir.",
                "Unser Team wächst. Deine Karriere auch?",
            ],
            "cta_examples": [
                "Link in Bio für mehr Infos!",
                "Schreib uns eine DM wenn du Teil des Teams werden willst!",
                "Tag jemanden der das lesen sollte!",
                "Speicher diesen Post für später!",
            ],
            "hashtags_permanent": ["#FörderkraftGmbH", "#Vertrieb", "#Sales", "#Direktvertrieb"],
        },

        "facebook": {
            "tone": "Nahbar, lokal, vertrauenswürdig, persönlich, gemeinschaftsorientiert",
            "anrede": "du/Sie (mix)",
            "style": "Lokale Präsenz stärken, Vertrauen aufbauen, Community aufbauen",
            "content_pillars": [
                "Lokale Erfolgsgeschichten",
                "Kundenstimmen & Referenzen",
                "Unternehmens-News",
                "Veranstaltungen & Events",
                "Team-Vorstellungen",
            ],
            "example_opening_lines": [
                "Wir sind wieder in [Stadt] unterwegs!",
                "Was unsere Kunden über uns sagen.",
                "Hinter jedem erfolgreichen Unternehmen steckt ein starkes Vertriebsteam.",
                "Neues aus unserem Team!",
            ],
            "cta_examples": [
                "Hinterlasst uns eine Nachricht für ein kostenloses Erstgespräch!",
                "Teilt diesen Post mit jemandem der das braucht!",
                "Was denkt ihr? Schreibt es in die Kommentare!",
            ],
            "hashtags_permanent": ["#FörderkraftGmbH", "#Direktvertrieb", "#Vertrieb"],
        },

        "tiktok": {
            "tone": "Energetisch, authentisch, unterhaltsam, jung, ungeschliffen",
            "anrede": "du",
            "style": "Echte Einblicke, Entertainment mit Mehrwert, Recruiting durch Kultur zeigen",
            "content_pillars": [
                "Ein Tag als Vertriebler (POV Videos)",
                "Lustige/ehrliche Momente im Außendienst",
                "Schnelle Sales-Tipps",
                "Team-Challenges & Wettbewerbe",
                "Erfolgsmomente feiern",
            ],
            "example_opening_lines": [
                "POV: Dein erster Tag bei uns",
                "Das sagt dir KEINER über Door-to-Door Sales...",
                "Wenn der Kunde Nein sagt aber du trotzdem gewinnst",
                "Unser Team verdient mehr als du denkst",
            ],
            "cta_examples": [
                "Folg uns für mehr Einblicke!",
                "Kommentier deine größte Sales-Lektion!",
                "DM uns wenn du bei uns starten willst!",
            ],
            "hashtags_permanent": ["#FörderkraftGmbH", "#Sales", "#Vertrieb", "#Karriere"],
        },

        "twitter": {
            "tone": "Direkt, meinungsstark, informativ, prägnant, selbstbewusst",
            "anrede": "du",
            "style": "Thought Leadership in kurz - Meinungen, Tipps, Branchennews",
            "content_pillars": [
                "Kontroverse Vertriebsmeinungen",
                "Schnelle Vertriebstipps",
                "Branchen-Kommentare",
                "Recruiting-Statements",
                "Unternehmens-Meilensteine",
            ],
            "example_opening_lines": [
                "Unpopular opinion: Kaltakquise ist effektiver als LinkedIn Ads.",
                "3 Dinge die jeder Vertriebler wissen muss:",
                "Wir suchen Menschen die Nein als Motivation sehen.",
                "Digitales Marketing ersetzt keine menschliche Verbindung.",
            ],
            "cta_examples": [
                "Was denkst du? Retweet wenn du zustimmst.",
                "Folg uns für tägliche Vertriebstipps.",
                "DM uns für ein Gespräch.",
            ],
            "hashtags_permanent": ["#FörderkraftGmbH", "#Sales", "#Vertrieb"],
        },
    },

    # --------------------------------------------------------
    # FAQ - Häufige Fragen (werden aus brand_knowledge.json geladen)
    # --------------------------------------------------------
    "faq": {
        "Was macht ihr?": "Bitte den Fragebogen unter /fragebogen ausfüllen um die Marke zu konfigurieren.",
        "Wie erreiche ich euch?": "Noch nicht konfiguriert.",
    },
}

# Backward compatibility: module-level BRAND points to defaults
BRAND = _DEFAULTS


def _brand_slug(name: str) -> str:
    """Convert brand name to a hashtag-safe slug."""
    slug = name.replace("GmbH", "").replace("gmbh", "")
    slug = re.sub(r"[.\s]+", "", slug)
    return slug.strip()


def get_brand() -> dict:
    """
    Returns the active brand config, merging client/brand_knowledge.json
    over the _DEFAULTS.  Falls back to _DEFAULTS if the file is missing
    or invalid.
    """
    import copy
    brand = copy.deepcopy(_DEFAULTS)

    bk_file = Path("client/brand_knowledge.json")
    if not bk_file.exists():
        return brand

    try:
        bk = json.loads(bk_file.read_text(encoding="utf-8"))
    except Exception:
        return brand

    # --- scalar fields ---
    if bk.get("brand_name"):
        brand["name"] = str(bk["brand_name"]).strip()
    if bk.get("slogan"):
        brand["slogan"] = str(bk["slogan"]).strip()
    if bk.get("industry"):
        brand["industry"] = str(bk["industry"]).strip()
    if bk.get("mission"):
        brand["core_service"] = str(bk["mission"]).strip()

    # --- list fields ---
    values = bk.get("values")
    if isinstance(values, list) and any(v for v in values if v):
        brand["values"] = [str(v) for v in values if str(v).strip()]

    usp = bk.get("usp")
    if isinstance(usp, list) and any(u for u in usp if u):
        brand["usp"] = [str(u) for u in usp if str(u).strip()]

    # --- tone ---
    tone_keywords = bk.get("tone_keywords")
    if tone_keywords:
        if isinstance(tone_keywords, list):
            brand["general_tone"]["personality"] = ", ".join(
                str(t) for t in tone_keywords if str(t).strip()
            )
        else:
            brand["general_tone"]["personality"] = str(tone_keywords)

    avoid_words = bk.get("avoid_words")
    if isinstance(avoid_words, list) and avoid_words:
        brand["general_tone"]["avoid"] = [str(a) for a in avoid_words if str(a).strip()]

    # --- faq ---
    faq = bk.get("faq")
    if isinstance(faq, dict) and faq:
        brand["faq"] = faq

    # --- content_pillars → all platform_voices ---
    pillars = bk.get("content_pillars")
    if isinstance(pillars, list) and len(pillars) >= 3:
        pillar_strs = [str(p) for p in pillars]
        for platform in brand["platform_voices"]:
            brand["platform_voices"][platform]["content_pillars"] = pillar_strs

    # --- replace "Förderkraft" hashtags with brand slug ---
    slug = _brand_slug(brand["name"])
    if slug and slug != "Förderkraft":
        for platform in brand["platform_voices"]:
            old_tags = brand["platform_voices"][platform].get("hashtags_permanent", [])
            new_tags = []
            for tag in old_tags:
                if "Förderkraft" in tag:
                    new_tags.append(f"#{slug}")
                else:
                    new_tags.append(tag)
            brand["platform_voices"][platform]["hashtags_permanent"] = new_tags

    return brand


def get_platform_voice(platform: str) -> dict:
    """Gibt die Brand Voice für eine spezifische Plattform zurück"""
    return get_brand()["platform_voices"].get(platform, {})


def get_brand_context(platform: str) -> str:
    """Erstellt einen vollständigen Kontext-String für die KI"""
    brand = get_brand()
    voice = get_platform_voice(platform)
    faq_text = "\n".join([f"- {q}: {a}" for q, a in brand["faq"].items()])

    return f"""
MARKE: {brand['name']}
SLOGAN: {brand['slogan']}
BRANCHE: {brand['industry']} | {brand['core_service']}

MARKENWERTE: {', '.join(brand['values'])}

USPs:
{chr(10).join(['- ' + u for u in brand['usp']])}

PLATTFORM: {platform.upper()}
TON: {voice.get('tone', '')}
ANREDE: {voice.get('anrede', 'du')}
STIL: {voice.get('style', '')}

CONTENT SÄULEN:
{chr(10).join(['- ' + c for c in voice.get('content_pillars', [])])}

IMMER VERMEIDEN:
{chr(10).join(['- ' + a for a in brand['general_tone']['avoid']])}

HÄUFIGE FRAGEN & ANTWORTEN:
{faq_text}

FESTE HASHTAGS: {' '.join(voice.get('hashtags_permanent', []))}
"""
