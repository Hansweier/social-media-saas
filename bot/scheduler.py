"""
Scheduler — Herzstück des Bots.
Läuft dauerhaft und koordiniert:
  - Automatisches Content-Generieren & Posten nach Zeitplan
  - Kommentare & DMs beantworten (alle 15 Min)
  - Täglicher Analytics-Report (abends)
  - Wöchentlicher Content-Kalender (montags)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import schedule
import time
import logging
from datetime import datetime

from bot.poster import Poster
from bot.content_calendar import ContentCalendar
from bot.dm_handler import DMHandler
from bot.analytics import Analytics

import smtplib
from email.mime.text import MIMEText


def _brand_name() -> str:
    try:
        from brand.foerderkraft_brand import get_brand
        return get_brand().get("name", "Sozibot")
    except Exception:
        return "Sozibot"


def _send_notify(config: dict, subject: str, body: str):
    """Sendet E-Mail-Benachrichtigung wenn SMTP konfiguriert."""
    smtp_email = config.get("notify", {}).get("smtp_email")
    smtp_pass  = config.get("notify", {}).get("smtp_password")
    to_email   = config.get("notify", {}).get("email")
    if not smtp_email or not smtp_pass or "dein" in str(smtp_pass):
        return  # nicht konfiguriert
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[{_brand_name()} Bot] {subject}"
        msg["From"]    = smtp_email
        msg["To"]      = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as s:
            s.login(smtp_email, smtp_pass)
            s.sendmail(smtp_email, to_email, msg.as_string())
        log.info(f"E-Mail gesendet: {subject}")
    except Exception as e:
        log.warning(f"E-Mail fehlgeschlagen: {e}")

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, config: dict):
        self.config  = config
        self.poster   = Poster(config)
        self.calendar = ContentCalendar()
        self.dm       = DMHandler(config["claude"]["api_key"], config=config)
        self.analytics = Analytics()

        self._post_schedule = config["posting"]["schedule"]  # {platform: ["HH:MM", ...]}

    # ─── Posting ─────────────────────────────────────────────────────────────

    def _post_platform(self, platform: str):
        """Generiert und postet für eine Plattform wenn Posts vorhanden sind."""
        # Pause-Check: Plattform vom Nutzer deaktiviert?
        try:
            from dashboard.services.variant_service import get_paused_platforms
            if platform in get_paused_platforms():
                log.info(f"[{platform}] Pausiert — überspringe.")
                return
        except Exception:
            pass

        # TikTok: Video-Upload noch nicht implementiert — überspringen statt fehler
        if platform == "tiktok":
            log.info("[tiktok] Video-Upload nicht implementiert — überspringe.")
            return

        # Modus laden
        from dashboard.services.variant_service import get_mode
        mode = get_mode()

        # 1. Schaue, ob ein geplanter Post im Kalender wartet
        all_upcoming = self.calendar.get_upcoming_posts(days=1)
        upcoming = [p for p in all_upcoming if p.get("platform") == platform][:1]

        # Co-Pilot: nur freigegebene Posts posten
        if mode == "copilot":
            upcoming = [p for p in upcoming if p.get("approval_status") == "freigegeben"]

        if upcoming:
            entry = upcoming[0]
            topic   = entry.get("topic", "")
            content = entry.get("content", "")

            # Content generieren falls noch nicht vorhanden
            if not content:
                log.info(f"[{platform}] Generiere Content für: {topic[:60]}")
                try:
                    content = self.poster.generate_content(platform, topic)
                    self.calendar.update_post(entry["id"], content=content, status="generiert")
                except Exception as e:
                    log.error(f"[{platform}] Content-Generierung fehlgeschlagen: {e}")
                    return

            # Posten
            log.info(f"[{platform}] Poste: {content[:80]}...")
            result = self.poster.post(platform, content, topic)

            if result["success"]:
                self.calendar.update_post(entry["id"], status="gepostet", post_id=result.get("post_id"))
                self.analytics.track_post(platform, result.get("post_id", ""), topic)
                log.info(f"[{platform}] Erfolgreich gepostet! ID: {result.get('post_id')}")
                _send_notify(self.config,
                    f"✓ {platform.capitalize()} — Post veröffentlicht",
                    f"Thema: {topic}\n\nInhalt:\n{content[:300]}\n\nPost-ID: {result.get('post_id')}")
            else:
                self.calendar.update_post(entry["id"], status="fehler", error=result.get("error"))
                log.error(f"[{platform}] Posting fehlgeschlagen: {result.get('error')}")
                _send_notify(self.config,
                    f"✗ {platform.capitalize()} — Posting fehlgeschlagen",
                    f"Thema: {topic}\nFehler: {result.get('error')}\n\nBitte prüfe das Dashboard.")

        else:
            # Auto-Pilot ohne Kalender: Topic aus Rotation, KEIN neuen Plan generieren
            if mode == "autopilot":
                log.info(f"[{platform}] Auto-Pilot: kein geplanter Post — nehme Topic aus Rotation...")
                try:
                    import random
                    topics = self.calendar.topic_rotation.get(platform, [_brand_name()])
                    topic  = random.choice(topics)
                    content = self.poster.generate_content(platform, topic)
                    log.info(f"[{platform}] Poste (Auto-Pilot Rotation): {content[:80]}...")
                    result = self.poster.post(platform, content, topic)
                    if result["success"]:
                        self.calendar.add_post(platform, topic, datetime.now(), content=content, status="gepostet")
                        self.analytics.track_post(platform, result.get("post_id", ""), topic)
                        log.info(f"[{platform}] Erfolgreich gepostet! ID: {result.get('post_id')}")
                    else:
                        log.error(f"[{platform}] Posting fehlgeschlagen: {result.get('error')}")
                except Exception as e:
                    log.error(f"[{platform}] Fehler: {e}")
            else:
                log.info(f"[{platform}] Co-Pilot: kein freigegebener Post — überspringe.")

    # ─── Just-in-Time Generation ─────────────────────────────────────────────

    def _check_jit_generation(self):
        """
        Just-in-Time: Generiert Varianten für Posts die in den nächsten
        jit_hours_before Stunden anstehen und noch keine Varianten haben.
        Schickt danach Benachrichtigung zur Freigabe.
        """
        try:
            from dashboard.services.variant_service import get_generation_config, VariantService
            cfg = get_generation_config()
            if cfg["mode"] != "jit":
                return

            from datetime import timedelta
            from bot.content_calendar import ContentCalendar
            hours   = cfg["hours_before"]
            now     = datetime.now()
            cutoff  = now + timedelta(hours=hours)
            cal     = ContentCalendar()
            upcoming = cal.get_upcoming_posts(days=max(2, hours // 24 + 1))

            for post in upcoming:
                if post.get("variants"):
                    continue
                try:
                    scheduled = datetime.fromisoformat(post["scheduled_time"])
                except Exception:
                    continue
                if not (now <= scheduled <= cutoff):
                    continue

                log.info(f"[JIT] Generiere Varianten: {post['id']} ({post['platform']})")
                try:
                    svc      = VariantService(self.config["claude"]["api_key"])
                    variants = svc.generate_variants(post["platform"], post.get("topic", ""))
                    cal.update_post(
                        post["id"],
                        variants=variants,
                        content=next((v["content"] for v in variants if v["selected"]), None),
                        selected_variant_id=next((v["variant_id"] for v in variants if v["selected"]), None),
                        approval_status="pending",
                    )
                    from dashboard.services.notification_service import push
                    push(
                        notif_type="approval_needed",
                        message=f"{post['platform'].capitalize()} Post um "
                                f"{scheduled.strftime('%H:%M')} Uhr — Variante auswählen",
                        post_id=post["id"],
                        platform=post["platform"],
                        scheduled_time=post["scheduled_time"],
                    )
                    log.info(f"[JIT] ✓ Varianten + Notification für {post['id']}")
                except Exception as e:
                    log.error(f"[JIT] Fehler für {post['id']}: {e}")
        except Exception as e:
            log.error(f"[JIT] Allgemeiner Fehler: {e}")

    # ─── Engagement ──────────────────────────────────────────────────────────

    def check_and_reply(self):
        """Kommentare & DMs auf allen Plattformen prüfen und beantworten."""
        log.info("Prüfe Kommentare & DMs...")

        try:
            self._reply_instagram()
        except Exception as e:
            log.error(f"Instagram Engagement-Check fehlgeschlagen: {e}")

        try:
            self._reply_twitter()
        except Exception as e:
            log.error(f"Twitter Engagement-Check fehlgeschlagen: {e}")

        try:
            self._reply_facebook()
        except Exception as e:
            log.error(f"Facebook Engagement-Check fehlgeschlagen: {e}")

        try:
            self._reply_linkedin()
        except Exception as e:
            log.error(f"LinkedIn Engagement-Check fehlgeschlagen: {e}")

    def _reply_instagram(self):
        from platforms.instagram.instagram_api import InstagramAPI
        from platforms.instagram.instagram_content import InstagramContent

        cfg = self.config["instagram"]
        if not cfg["access_token"] or "dein_token" in cfg["access_token"]:
            return

        api = InstagramAPI(cfg["access_token"], cfg["account_id"])
        gen = InstagramContent(self.config["claude"]["api_key"])

        # Mentions beantworten
        mentions = api.get_mentions() or []
        for m in mentions[:5]:
            reply = gen.reply_to_comment(m.get("text", ""), _brand_name())
            api.reply_to_comment(m["id"], reply)
            self.analytics.track_interaction("instagram", "mention_reply")
            log.info(f"Instagram Mention beantwortet: {m['id']}")

    def _reply_twitter(self):
        from platforms.twitter.twitter_api import TwitterAPI
        from platforms.twitter.twitter_content import TwitterContent

        cfg = self.config["twitter"]
        if not cfg["api_key"] or "dein" in cfg["api_key"]:
            return

        api = TwitterAPI(
            cfg["api_key"], cfg["api_secret"],
            cfg["access_token"], cfg["access_token_secret"],
            cfg["bearer_token"]
        )
        gen = TwitterContent(self.config["claude"]["api_key"])

        mentions = api.get_mentions() or []
        for m in mentions[:5]:
            reply = gen.reply_to_mention(m.get("text", ""))
            api.reply_to_tweet(m["id"], reply)
            self.analytics.track_interaction("twitter", "mention_reply")
            log.info(f"Twitter Mention beantwortet: {m['id']}")

    def _reply_facebook(self):
        from platforms.facebook.facebook_api import FacebookAPI
        from platforms.facebook.facebook_content import FacebookContent

        cfg = self.config["facebook"]
        if not cfg["access_token"] or "dein_token" in cfg["access_token"]:
            return

        api = FacebookAPI(cfg["access_token"], cfg["page_id"])
        gen = FacebookContent(self.config["claude"]["api_key"])

        posts = api.get_posts() or []
        for post in posts[:3]:
            comments = api.get_comments(post["id"]) or []
            for c in comments[:3]:
                reply = gen.reply_to_comment(c.get("message", ""))
                api.reply_to_comment(c["id"], reply)
                self.analytics.track_interaction("facebook", "comment_reply")
                log.info(f"Facebook Kommentar beantwortet: {c['id']}")

    def _reply_linkedin(self):
        from platforms.linkedin.linkedin_api import LinkedInAPI
        from platforms.linkedin.linkedin_content import LinkedInContent

        cfg = self.config["linkedin"]
        if not cfg["access_token"] or "dein_token" in cfg["access_token"]:
            return

        api = LinkedInAPI(cfg["access_token"])
        gen = LinkedInContent(self.config["claude"]["api_key"])

        person_id = cfg.get("person_id", "")
        comments = api.get_comments("recent") or []
        for c in comments[:3]:
            text  = c.get("message", {}).get("text", "")
            reply = gen.reply_to_comment(text)
            # LinkedInAPI.reply_to_comment(post_id, comment_id, text, person_id)
            post_id = c.get("postUrn", "recent")
            api.reply_to_comment(post_id, c["id"], reply, person_id)
            self.analytics.track_interaction("linkedin", "comment_reply")
            log.info(f"LinkedIn Kommentar beantwortet: {c['id']}")

    # ─── Media Queue ─────────────────────────────────────────────────────────

    def post_approved_media(self):
        """Postet alle approved Media-Queue-Einträge."""
        import json
        from pathlib import Path
        queue_dir = Path("client/media/queue")
        if not queue_dir.exists():
            return

        for manifest_path in queue_dir.glob("*.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("queue_status") != "approved":
                    continue

                platform  = manifest.get("platform", "instagram")
                topics    = manifest.get("suggested_topics", [])
                topic     = topics[0] if topics else _brand_name()
                processed = manifest.get("processed_path", "")

                log.info(f"[Queue] Poste Media: {manifest['media_id']} auf {platform}")
                content = self.poster.generate_content(platform, topic)
                result  = self.poster.post(platform, content, topic, image_url=processed)

                if result["success"]:
                    manifest["queue_status"] = "posted"
                    self.analytics.track_post(platform, result.get("post_id", ""), topic)
                    log.info(f"[Queue] Erfolgreich gepostet: {result.get('post_id')}")
                else:
                    manifest["queue_status"] = "fehler"
                    manifest["error"] = result.get("error")
                    log.error(f"[Queue] Posting fehlgeschlagen: {result.get('error')}")

                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            except Exception as e:
                log.error(f"[Queue] Fehler bei {manifest_path.name}: {e}")

    # ─── Reports ─────────────────────────────────────────────────────────────

    def daily_report(self):
        """Täglicher Analytics-Report in der Konsole und per E-Mail."""
        log.info("=== TÄGLICHER REPORT ===")
        self.analytics.print_dashboard()
        # E-Mail Report
        try:
            report = self.analytics.generate_weekly_report()
            lines = []
            for plat, s in report["plattformen"].items():
                if "message" not in s:
                    lines.append(f"{plat.upper()}: {s.get('posts_veroeffentlicht',0)} Posts, "
                                 f"Engagement: {s.get('durchschnittliche_engagement_rate','0%')}")
            if lines:
                _send_notify(self.config, "📊 Täglicher Report",
                             f"{_brand_name()} Bot — Heutiger Report:\n\n" + "\n".join(lines) +
                             "\n\nDetails im Dashboard unter /analytics/")
        except Exception as e:
            log.warning(f"Report-E-Mail fehlgeschlagen: {e}")

    def weekly_plan(self):
        """Montags neuen Content-Kalender generieren + Varianten für Co-Pilot."""
        log.info("=== WÖCHENTLICHER CONTENT-PLAN ===")
        self.calendar.generate_weekly_plan()
        self.calendar.print_calendar()

        from dashboard.services.variant_service import get_mode, VariantService
        if get_mode() == "copilot":
            log.info("Co-Pilot: Generiere 3 Varianten pro Post-Slot...")
            svc   = VariantService(self.config["claude"]["api_key"])
            posts = self.calendar.get_upcoming_posts(days=7)
            for post in posts:
                if post.get("variants"):
                    continue  # bereits generiert
                try:
                    variants = svc.generate_variants(post["platform"], post.get("topic", ""))
                    self.calendar.update_post(
                        post["id"],
                        variants=variants,
                        content=next((v["content"] for v in variants if v["selected"]), None),
                        selected_variant_id=next((v["variant_id"] for v in variants if v["selected"]), None),
                    )
                    log.info(f"Varianten generiert: {post['id']}")
                except Exception as e:
                    log.error(f"Varianten-Generierung fehlgeschlagen für {post['id']}: {e}")

    # ─── Start ───────────────────────────────────────────────────────────────

    def setup_schedule(self):
        """Alle Jobs nach Plattform-Zeitplan registrieren."""

        # Posting-Jobs pro Plattform
        for platform, times in self._post_schedule.items():
            for t in times:
                schedule.every().day.at(t).do(self._post_platform, platform=platform)
                log.info(f"Geplant: {platform} @ {t} Uhr")

        # Engagement alle 15 Minuten
        schedule.every(15).minutes.do(self.check_and_reply)

        # Media-Queue alle 5 Minuten prüfen (approved → posten)
        schedule.every(5).minutes.do(self.post_approved_media)

        # Just-in-Time Generierung alle 30 Minuten
        schedule.every(30).minutes.do(self._check_jit_generation)

        # Täglicher Report um 21:00
        schedule.every().day.at("21:00").do(self.daily_report)

        # Wöchentlicher Plan montags um 07:00
        schedule.every().monday.at("07:00").do(self.weekly_plan)

        log.info("Alle Jobs registriert.")

    def run(self):
        """Startet den Scheduler (blockierend)."""
        log.info("=" * 60)
        log.info(f"{_brand_name()} — Social Media Bot GESTARTET")
        log.info(f"Zeit: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        log.info("=" * 60)

        self.setup_schedule()

        # Einmaliger Engagement-Check beim Start
        self.check_and_reply()

        log.info("Bot läuft. Drücke CTRL+C zum Beenden.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)
        except KeyboardInterrupt:
            log.info("Bot gestoppt.")


def start_scheduler(config: dict):
    """Kompatibilitäts-Wrapper für alten Code."""
    Scheduler(config).run()
