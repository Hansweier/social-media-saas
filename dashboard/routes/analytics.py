from flask import Blueprint, render_template, request
from bot.analytics import Analytics
import json

bp = Blueprint("analytics", __name__, url_prefix="/analytics")
PLATFORMS = ["instagram", "facebook", "linkedin", "twitter", "tiktok"]


@bp.route("/")
def analytics_view():
    days = int(request.args.get("days", 30))
    analytics = Analytics()
    summaries = {p: analytics.get_platform_summary(p, days=days) for p in PLATFORMS}
    chart_data = json.dumps({
        p: s.get("posts_veroeffentlicht", 0) for p, s in summaries.items()
    })
    return render_template("analytics.html", summaries=summaries, chart_data=chart_data, days=days)
