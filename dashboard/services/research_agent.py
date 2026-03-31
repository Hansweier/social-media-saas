"""
Research Agent — Nutzt den Claude Agent SDK für automatische Themenrecherche.
Sucht nach aktuellen Trends in der Branche des Kunden und schlägt passende
Content-Themen vor. Läuft als Hintergrund-Task.
"""
import anyio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

RESEARCH_FILE = Path("client/research_suggestions.json")


def _load_brand_context() -> dict:
    try:
        bk = json.loads(Path("client/brand_knowledge.json").read_text(encoding="utf-8"))
        return {
            "brand_name": bk.get("brand_name", "Meine Marke"),
            "industry":   bk.get("industry", ""),
            "current_pillars": bk.get("content_pillars", []),
        }
    except Exception:
        return {"brand_name": "Meine Marke", "industry": "", "current_pillars": []}


async def _run_research(brand_name: str, industry: str, current_pillars: list) -> dict:
    """Startet den Agent SDK Research-Job mit WebSearch + WebFetch."""
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

    pillars_str  = ", ".join(current_pillars) if current_pillars else "noch keine definiert"
    industry_str = f" ({industry})" if industry else ""

    prompt = f"""Du bist ein Social-Media-Content-Stratege für {brand_name}{industry_str}.

Aktuelle Content-Säulen: {pillars_str}

Aufgabe:
1. Suche im Web nach den 3-5 aktuellsten Trends in der Branche "{industry or 'Social Media / Marketing'}"
2. Leite 8 konkrete Content-Themen ab die gut zu {brand_name} passen würden

Antworte am Ende EXAKT mit diesem JSON-Block:
```json
{{
  "trends": ["Trend 1", "Trend 2", "Trend 3"],
  "suggested_topics": [
    "Thema 1", "Thema 2", "Thema 3", "Thema 4",
    "Thema 5", "Thema 6", "Thema 7", "Thema 8"
  ],
  "reasoning": "1-2 Sätze warum diese Themen jetzt relevant sind"
}}
```"""

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch"],
            max_turns=10,
        )
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result

    # JSON aus Ergebnis extrahieren
    for pattern in [
        r'```json\s*(\{.*?\})\s*```',
        r'(\{[\s\S]*?"suggested_topics"[\s\S]*?\})',
    ]:
        m = re.search(pattern, result_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue

    log.error(f"[Research] Kein gültiges JSON in Ergebnis: {result_text[:200]}")
    return {"trends": [], "suggested_topics": [], "reasoning": result_text[:300]}


def run_research_sync() -> dict:
    """
    Synchroner Einstiegspunkt — führt den Agent-SDK-Research aus.
    Speichert Ergebnisse in client/research_suggestions.json.
    Sendet Benachrichtigung wenn fertig.
    """
    ctx = _load_brand_context()
    log.info(f"[Research] Starte Trend-Recherche für {ctx['brand_name']}...")

    try:
        result = anyio.run(
            _run_research,
            ctx["brand_name"],
            ctx["industry"],
            ctx["current_pillars"],
        )
        result["researched_at"] = datetime.now().isoformat()
        result["status"]        = "done"
    except ImportError:
        log.error("[Research] claude-agent-sdk nicht installiert")
        result = {
            "status": "error",
            "error": "claude-agent-sdk nicht installiert — pip install claude-agent-sdk",
        }
    except Exception as e:
        log.error(f"[Research] Fehler: {e}")
        result = {"status": "error", "error": str(e)}

    RESEARCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESEARCH_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if result.get("status") == "done" and result.get("suggested_topics"):
        try:
            from dashboard.services.notification_service import push
            push(
                notif_type="research_done",
                message=f"Trend-Recherche abgeschlossen — {len(result['suggested_topics'])} neue Themen vorgeschlagen",
                link="/einstellungen/marke",
            )
        except Exception:
            pass

    return result


def load_latest_research() -> dict:
    """Lädt die zuletzt gespeicherten Recherche-Ergebnisse."""
    try:
        if RESEARCH_FILE.exists():
            return json.loads(RESEARCH_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}
