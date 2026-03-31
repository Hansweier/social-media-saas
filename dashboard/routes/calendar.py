from flask import Blueprint, render_template, request, jsonify
from bot.content_calendar import ContentCalendar
from bot.poster import Poster
from bot.config import load_config
from datetime import datetime, timedelta, date as _date
import threading

bp = Blueprint("calendar", __name__, url_prefix="/calendar")

PLATFORMS = ["instagram", "facebook", "linkedin", "twitter", "tiktok"]
PLATFORM_ICONS = {
    "instagram": "📸", "facebook": "👍",
    "linkedin": "💼", "twitter": "🐦", "tiktok": "🎵",
}
PLATFORM_COLORS = {
    "instagram": "#e1306c", "facebook": "#1877f2",
    "linkedin":  "#0a66c2", "twitter":  "#1da1f2", "tiktok": "#ff0050",
}
DAY_NAMES_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _monday_of(d: _date) -> _date:
    return d - timedelta(days=d.weekday())


def _build_weeks(start: _date, num_weeks: int, by_day: dict) -> list:
    """
    Gibt eine Liste von Wochen zurück.
    Jede Woche: {start, end, label, kw, days: [{date, name, posts}]}
    """
    weeks = []
    for w in range(num_weeks):
        week_start = start + timedelta(weeks=w)
        days = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            posts = by_day.get(day.isoformat(), [])
            days.append({
                "date":    day,
                "iso":     day.isoformat(),
                "name":    DAY_NAMES_DE[d],
                "posts":   sorted(posts, key=lambda p: p.get("scheduled_time", "")),
                "is_today": day == _date.today(),
                "is_past":  day < _date.today(),
            })
        weeks.append({
            "start": week_start,
            "end":   week_start + timedelta(days=6),
            "kw":    week_start.isocalendar()[1],
            "days":  days,
            "total":       sum(len(d["posts"]) for d in days),
            "approved":    sum(1 for day in days for p in day["posts"] if p.get("approval_status") == "freigegeben"),
            "pending":     sum(1 for day in days for p in day["posts"] if p.get("approval_status") == "pending"),
            "rejected":    sum(1 for day in days for p in day["posts"] if p.get("approval_status") == "abgelehnt"),
        })
    return weeks


def _build_archive(cal: ContentCalendar) -> list:
    """
    Vergangene 12 Monate als Liste von Monaten.
    Jeder Monat: {year, month, label, posts, stats}
    """
    today = _date.today()
    months = []
    for m in range(1, 13):    # 1 = letzter Monat, 12 = vor 12 Monaten
        # Ziel-Monat berechnen
        month_num = today.month - m
        year      = today.year
        while month_num <= 0:
            month_num += 12
            year      -= 1

        first = _date(year, month_num, 1)
        if month_num == 12:
            last = _date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last = _date(year, month_num + 1, 1) - timedelta(days=1)

        posts = []
        for p in cal.calendar.get("posts", []):
            try:
                t = datetime.fromisoformat(p["scheduled_time"]).date()
                if first <= t <= last:
                    posts.append(p)
            except Exception:
                pass

        posts = sorted(posts, key=lambda p: p.get("scheduled_time", ""))

        months.append({
            "year":     year,
            "month":    month_num,
            "label":    first.strftime("%B %Y"),
            "posts":    posts,
            "gepostet": sum(1 for p in posts if p.get("status") in ("gepostet", "freigegeben")),
            "total":    len(posts),
        })

    return months


@bp.route("/")
def calendar_view():
    active_platform = request.args.get("p", "all")

    # 4 Wochen ab heute (Montag dieser Woche)
    start  = _monday_of(_date.today())
    end    = start + timedelta(weeks=4) - timedelta(days=1)

    cal    = ContentCalendar()
    by_day = cal.get_range_posts(start, end)

    # Fehlende Posts auffüllen (Deduplizierung)
    seen: dict = {k: {p["id"] for p in v} for k, v in by_day.items()}
    for post in cal.calendar.get("posts", []):
        try:
            t   = datetime.fromisoformat(post["scheduled_time"]).date()
            key = t.isoformat()
            if start <= t <= end and key in by_day and post["id"] not in seen.get(key, set()):
                by_day[key].append(post)
                seen.setdefault(key, set()).add(post["id"])
        except Exception:
            pass

    # Platform-Filter
    if active_platform != "all":
        by_day = {k: [p for p in v if p.get("platform") == active_platform]
                  for k, v in by_day.items()}

    weeks   = _build_weeks(start, 4, by_day)
    archive = _build_archive(cal)

    from dashboard.services.variant_service import get_platform_schedules, get_paused_platforms
    return render_template(
        "calendar.html",
        weeks=weeks,
        archive=archive,
        now=datetime.now(),
        today=_date.today(),
        active_platform=active_platform,
        platforms=PLATFORMS,
        platform_icons=PLATFORM_ICONS,
        platform_colors=PLATFORM_COLORS,
        schedules=get_platform_schedules(),
        paused_platforms=get_paused_platforms(),
    )


# ── Zeitplan ─────────────────────────────────────────────────────────────────

@bp.route("/zeitplan-speichern", methods=["POST"])
def save_schedule():
    data     = request.get_json(silent=True) or {}
    platform = data.get("platform", "").strip().lower()
    days     = data.get("days", [])
    times    = data.get("times", [])
    if platform not in set(PLATFORMS):
        return jsonify({"error": "Ungültige Plattform"}), 400
    if not days or not times:
        return jsonify({"error": "Tage und Uhrzeiten fehlen"}), 400
    from dashboard.services.variant_service import set_platform_schedule
    set_platform_schedule(platform, days, times)
    return jsonify({"ok": True})


# ── Woche generieren ──────────────────────────────────────────────────────────

@bp.route("/mehrwochen-generieren", methods=["POST"])
def generate_multi_week():
    from dashboard.services.plan_service import can_generate, track_post_generated
    allowed, reason = can_generate()
    if not allowed:
        return jsonify({"ok": False, "error": reason, "upgrade": True})

    data  = request.get_json(silent=True) or {}
    weeks = max(1, min(int(data.get("weeks", 4)), 8))
    cal   = ContentCalendar()
    start = datetime.now()
    total = 0
    for w in range(weeks):
        week_start = start + timedelta(weeks=w)
        plan = cal.generate_weekly_plan(start_date=week_start)
        total += len(plan)
        for _ in plan:
            track_post_generated()
    return jsonify({"ok": True, "posts_created": total, "weeks": weeks})


# ── Post-Aktionen ─────────────────────────────────────────────────────────────

@bp.route("/add", methods=["POST"])
def add_post():
    data = request.get_json(silent=True) or {}
    platform       = data.get("platform", "").strip()
    scheduled_time = data.get("scheduled_time", "").strip()
    if not platform or platform not in set(PLATFORMS):
        return jsonify({"error": f"Ungültige Plattform: '{platform}'"}), 400
    if not scheduled_time:
        return jsonify({"error": "scheduled_time fehlt"}), 400
    cal     = ContentCalendar()
    post_id = cal.add_post(
        platform=platform,
        topic=data.get("topic", ""),
        scheduled_time=scheduled_time,
        content=data.get("content"),
    )
    return jsonify({"ok": True, "post_id": post_id})


@bp.route("/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    cal   = ContentCalendar()
    posts = cal.calendar["posts"]
    before = len(posts)
    cal.calendar["posts"] = [p for p in posts if p["id"] != post_id]
    if len(cal.calendar["posts"]) == before:
        return jsonify({"error": "Post nicht gefunden"}), 404
    cal._save()
    return jsonify({"ok": True})


@bp.route("/trigger/<post_id>", methods=["POST"])
def trigger_post(post_id):
    cal   = ContentCalendar()
    entry = next((p for p in cal.calendar["posts"] if p["id"] == post_id), None)
    if not entry:
        return jsonify({"error": "Post nicht gefunden"}), 404

    def _post():
        config  = load_config()
        poster  = Poster(config)
        topic   = entry.get("topic", "")
        content = entry.get("content") or poster.generate_content(entry["platform"], topic)
        result  = poster.post(entry["platform"], content, topic)
        status  = "gepostet" if result["success"] else "fehler"
        cal.update_post(post_id, status=status, content=content)

    threading.Thread(target=_post, daemon=True).start()
    return jsonify({"ok": True, "status": "gestartet"})
