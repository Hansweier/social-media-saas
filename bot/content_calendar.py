import json
import os
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from brand.foerderkraft_brand import BRAND, get_platform_voice

_save_lock = threading.Lock()

class ContentCalendar:
    def __init__(self, calendar_file="client/content_calendar.json"):
        self.calendar_file = calendar_file
        self.calendar = self._load()
        self.schedule = self._load_schedule()
        self.topic_rotation = self._load_topic_rotation()

    def _load_schedule(self) -> dict:
        """Lädt den Posting-Plan aus bot_settings.json (mit Fallback auf Defaults)."""
        try:
            from dashboard.services.variant_service import get_platform_schedules
            schedules = get_platform_schedules()
            result = {}
            for platform, cfg in schedules.items():
                slots = []
                for day in cfg.get("days", []):
                    for t in cfg.get("times", []):
                        slots.append(f"{day} {t}")
                if slots:
                    result[platform] = slots
            return result
        except Exception:
            return {
                "linkedin":  ["MON 09:00", "WED 12:00", "FRI 09:00"],
                "instagram": ["MON 10:00", "WED 18:00", "FRI 17:00", "SUN 12:00"],
                "facebook":  ["TUE 10:00", "THU 18:00", "SAT 11:00"],
                "tiktok":    ["MON 17:00", "THU 17:00", "SAT 14:00"],
                "twitter":   ["MON 08:00", "TUE 12:00", "WED 08:00", "THU 12:00", "FRI 08:00"],
            }

    def _load_topic_rotation(self) -> dict:
        """Lädt Themen-Rotation — bevorzugt aus brand_knowledge.json, sonst generische Fallbacks."""
        rotation = {
            "linkedin": [
                "5 Dinge die wir in diesem Jahr gelernt haben",
                "Was Kunden wirklich von uns erwarten",
                "Recruiting: So findest du die besten Talente",
                "Erfolgsgeschichte: Ein Projekt das uns stolz macht",
                "5 Fehler die Unternehmen in unserer Branche machen",
                "Unser Wachstum: Was hat sich verändert?",
                "Die Zukunft unserer Branche",
            ],
            "instagram": [
                "Teamvorstellung: Wer steckt hinter uns?",
                "Behind the Scenes: Ein normaler Arbeitstag",
                "Motivation Monday: Was uns antreibt",
                "Erfolg feiern: Team-Meilenstein",
                "Recruiting-Post: Komm ins Team",
                "Kundenerfolg: Was wir gemeinsam erreicht haben",
                "Fun Fact über unsere Branche",
            ],
            "facebook": [
                "News: Was gibt es Neues bei uns?",
                "Lokaler Fokus: Wir sind für euch da",
                "Kundenstimme / Testimonial",
                "Team Event Rückblick",
                "Jobangebot: Wir suchen Verstärkung",
                "Tipp aus der Praxis",
            ],
            "tiktok": [
                "POV: Dein erster Tag bei uns",
                "Was man dir über unsere Branche NICHT erzählt",
                "Day in the Life: Alltag im Team",
                "Team Challenge / Wettbewerb",
                "Reaktion auf Branchenmythen",
                "Die Wahrheit über unseren Job",
            ],
            "twitter": [
                "Unpopular Opinion: Was in unserer Branche falsch läuft",
                "Täglicher Tipp aus der Praxis",
                "Branchen-News Kommentar",
                "Statement: Was uns wichtig ist",
                "Quick Win für unsere Zielgruppe",
            ],
        }
        # Override with brand_knowledge.json if available
        try:
            bk_file = Path("client/brand_knowledge.json")
            if bk_file.exists():
                bk = json.loads(bk_file.read_text(encoding="utf-8"))
                pillars    = bk.get("content_pillars") or []
                brand_name = bk.get("brand_name", "")
                if isinstance(pillars, list) and pillars:
                    for plat in rotation:
                        rotation[plat] = [str(p) for p in pillars[:8]]
                if brand_name:
                    for plat in rotation:
                        rotation[plat] = [
                            re.sub(r'\bFörderkraft\b', brand_name, t) for t in rotation[plat]
                        ]
        except Exception:
            pass
        return rotation

    def _load(self):
        if os.path.exists(self.calendar_file):
            with open(self.calendar_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"posts": [], "last_updated": None}

    def _save(self):
        """Thread-safe atomic save via temp-file + rename."""
        import tempfile
        os.makedirs(os.path.dirname(self.calendar_file), exist_ok=True)
        with _save_lock:
            dir_ = os.path.dirname(os.path.abspath(self.calendar_file))
            fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.calendar, f, ensure_ascii=False, indent=2, default=str)
                os.replace(tmp_path, self.calendar_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    def add_post(self, platform, topic, scheduled_time, content=None, status="geplant"):
        """Post zum Kalender hinzufügen"""
        post = {
            "id": f"{platform}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "platform": platform,
            "topic": topic,
            "content": content,
            "scheduled_time": str(scheduled_time),
            "status": status,  # geplant | generiert | freigegeben | gepostet | fehlgeschlagen | abgelehnt
            "created_at": str(datetime.now()),
            # Varianten-System
            "variants": [],
            "selected_variant_id": None,
            "approval_status": "pending",  # pending | freigegeben | abgelehnt
            "approved_at": None,
            "linked_media_id": None,
        }
        self.calendar["posts"].append(post)
        self.calendar["last_updated"] = str(datetime.now())
        self._save()
        return post["id"]

    def get_week_posts(self, week_start=None):
        """Posts einer Woche gruppiert nach Tag zurückgeben."""
        if week_start is None:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=7)
        result = {}
        for i in range(7):
            day = week_start + timedelta(days=i)
            result[day.isoformat()] = []
        for post in self.calendar["posts"]:
            try:
                t = datetime.fromisoformat(post["scheduled_time"]).date()
                key = t.isoformat()
                if key in result:
                    result[key].append(post)
            except Exception:
                pass
        return result

    def update_post(self, post_id, **kwargs):
        """Post updaten (Status, Content etc.)"""
        for post in self.calendar["posts"]:
            if post["id"] == post_id:
                post.update(kwargs)
                self._save()
                return True
        return False

    def get_upcoming_posts(self, days=7):
        """Geplante Posts der nächsten X Tage (geplant + freigegeben, nicht bereits gepostet)."""
        upcoming = []
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        postable = {"geplant", "generiert", "freigegeben"}
        for post in self.calendar["posts"]:
            if post.get("status") not in postable:
                continue
            try:
                scheduled = datetime.fromisoformat(post["scheduled_time"])
                if now <= scheduled <= cutoff:
                    upcoming.append(post)
            except Exception:
                pass
        return sorted(upcoming, key=lambda x: x["scheduled_time"])

    def get_range_posts(self, start_date, end_date) -> dict:
        """Posts zwischen zwei Daten, gruppiert nach Tag (YYYY-MM-DD)."""
        from datetime import date as _date
        result = {}
        current = start_date if isinstance(start_date, _date) else start_date.date()
        end     = end_date   if isinstance(end_date,   _date) else end_date.date()
        while current <= end:
            result[current.isoformat()] = []
            current += timedelta(days=1)
        for post in self.calendar["posts"]:
            try:
                t = datetime.fromisoformat(post["scheduled_time"]).date()
                key = t.isoformat()
                if key in result:
                    result[key].append(post)
            except Exception:
                pass
        return result

    def generate_weekly_plan(self, start_date=None):
        """Automatisch Wochenplan generieren"""
        if start_date is None:
            start_date = datetime.now()

        days = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
        plan = []

        for platform, times in self.schedule.items():
            topics = self.topic_rotation.get(platform, ["Allgemeiner Content"])
            if not topics:
                topics = ["Allgemeiner Content"]
            topic_idx = len([p for p in self.calendar["posts"] if p["platform"] == platform]) % len(topics)

            for time_slot in times:
                day_str, time_str = time_slot.split(" ")
                day_offset = (days[day_str] - start_date.weekday()) % 7
                post_date = start_date + timedelta(days=day_offset)
                hour, minute = map(int, time_str.split(":"))
                post_datetime = post_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                topic = topics[topic_idx % len(topics)]
                topic_idx += 1

                # Deduplication: skip if a non-posted entry already exists for this slot
                date_key = post_datetime.date().isoformat()
                already = any(
                    p for p in self.calendar["posts"]
                    if p["platform"] == platform
                    and p.get("scheduled_time", "")[:10] == date_key
                    and p.get("status") not in ("gepostet", "fehler")
                )
                if already:
                    continue

                post_id = self.add_post(platform, topic, post_datetime)
                plan.append({
                    "id": post_id,
                    "platform": platform,
                    "topic": topic,
                    "time": str(post_datetime)
                })

        return plan

    def print_calendar(self, days=7):
        """Kalender schön ausgeben"""
        upcoming = self.get_upcoming_posts(days)
        print(f"\n=== Content Kalender - Naechste {days} Tage ===\n")
        if not upcoming:
            print("Keine geplanten Posts gefunden.")
            return
        for post in upcoming:
            status_icon = {"geplant": "[  ]", "generiert": "[KI]", "gepostet": "[OK]", "fehlgeschlagen": "[!!]"}.get(post["status"], "[ ?]")
            print(f"{status_icon} {post['scheduled_time'][:16]} | {post['platform'].upper():10} | {post['topic'][:60]}")
        print()
