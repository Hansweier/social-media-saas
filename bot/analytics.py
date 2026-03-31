import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

class Analytics:
    """
    Analytics Dashboard für alle Plattformen.
    Trackt Posts, DMs, Kommentare und Engagement.
    """

    def __init__(self, analytics_file="client/analytics.json"):
        self.file = analytics_file
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                print(f"[Analytics] Korrupte analytics.json — wird zurückgesetzt.")
        return {
            "posts": [],
            "interactions": [],
            "weekly_summaries": [],
        }

    def _save(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)

    def track_post(self, platform, post_id, topic, likes=0, comments=0, shares=0, reach=0, saves=0, content=""):
        """Post-Performance tracken und Learning Engine informieren."""
        entry = {
            "timestamp": str(datetime.now()),
            "platform": platform,
            "post_id": post_id,
            "topic": topic,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "reach": reach,
            "saves": saves,
            "engagement_rate": round((likes + comments + shares + saves) / max(reach, 1) * 100, 2)
        }
        self.data["posts"].append(entry)
        self._save()

        # Performance-Signal an Learning Engine weitergeben
        try:
            from dashboard.services.learning_service import record_performance
            record_performance(
                post_id=post_id, platform=platform, topic=topic, content=content,
                likes=likes, comments=comments, shares=shares, reach=reach, saves=saves,
            )
        except Exception:
            pass

    def track_interaction(self, platform, interaction_type, intent=None, escalated=False):
        """
        Interaktion tracken (DM, Kommentar, Mention)
        interaction_type: dm | comment | mention
        """
        entry = {
            "timestamp": str(datetime.now()),
            "platform": platform,
            "type": interaction_type,
            "intent": intent,
            "escalated": escalated,
        }
        self.data["interactions"].append(entry)
        self._save()

    def get_platform_summary(self, platform, days=30):
        """Zusammenfassung für eine Plattform"""
        cutoff = datetime.now() - timedelta(days=days)

        def _ts(entry):
            try:
                return datetime.fromisoformat(entry["timestamp"])
            except Exception:
                return datetime.min

        posts = [p for p in self.data["posts"]
                 if p["platform"] == platform
                 and _ts(p) >= cutoff]

        interactions = [i for i in self.data["interactions"]
                        if i["platform"] == platform
                        and _ts(i) >= cutoff]

        if not posts:
            return {"platform": platform, "message": "Noch keine Daten"}

        total_reach      = sum(p["reach"] for p in posts)
        total_likes      = sum(p["likes"] for p in posts)
        total_comments   = sum(p["comments"] for p in posts)
        total_shares     = sum(p["shares"] for p in posts)
        avg_engagement   = sum(p["engagement_rate"] for p in posts) / len(posts)

        best_post = max(posts, key=lambda x: x["engagement_rate"])

        intent_counts = defaultdict(int)
        for i in interactions:
            if i["intent"]:
                intent_counts[i["intent"]] += 1

        return {
            "platform": platform,
            "zeitraum_tage": days,
            "posts_veroeffentlicht": len(posts),
            "gesamte_reichweite": total_reach,
            "gesamte_likes": total_likes,
            "gesamte_kommentare": total_comments,
            "gesamte_shares": total_shares,
            "durchschnittliche_engagement_rate": f"{avg_engagement:.2f}%",
            "interaktionen_gesamt": len(interactions),
            "interaktionen_nach_absicht": dict(intent_counts),
            "eskalationen": sum(1 for i in interactions if i.get("escalated")),
            "bester_post": {
                "thema": best_post["topic"],
                "engagement_rate": f"{best_post['engagement_rate']}%",
                "datum": best_post["timestamp"][:10],
            }
        }

    def print_dashboard(self, days=30):
        """Übersichtliches Dashboard ausgeben"""
        print(f"\n{'='*60}")
        print(f"  FOERDERKRAFT GMBH - ANALYTICS DASHBOARD")
        print(f"  Zeitraum: Letzte {days} Tage")
        print(f"{'='*60}\n")

        platforms = ["instagram", "linkedin", "facebook", "tiktok", "twitter"]
        for platform in platforms:
            summary = self.get_platform_summary(platform, days)
            if "message" in summary:
                continue

            print(f"  [{platform.upper()}]")
            print(f"  Posts:          {summary['posts_veroeffentlicht']}")
            print(f"  Reichweite:     {summary['gesamte_reichweite']:,}")
            print(f"  Engagement:     {summary['durchschnittliche_engagement_rate']}")
            print(f"  Interaktionen:  {summary['interaktionen_gesamt']}")
            if summary['eskalationen'] > 0:
                print(f"  [!] Eskalationen: {summary['eskalationen']}")
            print(f"  Bester Post:    {summary['bester_post']['thema'][:45]}...")
            print()

    def generate_weekly_report(self):
        """Wöchentlichen Report generieren"""
        report = {
            "erstellt_am": str(datetime.now()),
            "zeitraum": "letzte 7 Tage",
            "plattformen": {}
        }

        for platform in ["instagram", "linkedin", "facebook", "tiktok", "twitter"]:
            report["plattformen"][platform] = self.get_platform_summary(platform, 7)

        # Report speichern
        report_file = f"client/reports/weekly_{datetime.now().strftime('%Y%m%d')}.json"
        os.makedirs("client/reports", exist_ok=True)
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report
