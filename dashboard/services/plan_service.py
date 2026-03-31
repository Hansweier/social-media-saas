"""
Plan Service — Verwaltet Subscription-Pläne, Usage-Tracking und Feature-Gates.

Pläne:
  trial   — 14 Tage kostenlos, 30 Posts, 3 Plattformen
  starter — €79/Monat, 150 Posts, 3 Plattformen
  pro     — €149/Monat, unbegrenzt, 5 Plattformen + DM + Vision + Trends
  agency  — €349/Monat, unbegrenzt, alles × 5 Marken
"""
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

SETTINGS_FILE = Path("client/bot_settings.json")

PLANS: dict = {
    "trial": {
        "name":          "Trial",
        "max_posts":     30,
        "max_platforms": 3,
        "dm_handler":    False,
        "vision":        False,
        "research":      False,
        "price_eur":     0,
        "label":         "14 Tage kostenlos",
    },
    "starter": {
        "name":          "Starter",
        "max_posts":     150,
        "max_platforms": 3,
        "dm_handler":    False,
        "vision":        True,
        "research":      False,
        "price_eur":     79,
        "label":         "€79 / Monat",
    },
    "pro": {
        "name":          "Pro",
        "max_posts":     None,   # unbegrenzt
        "max_platforms": 5,
        "dm_handler":    True,
        "vision":        True,
        "research":      True,
        "price_eur":     149,
        "label":         "€149 / Monat",
    },
    "agency": {
        "name":          "Agency",
        "max_posts":     None,
        "max_platforms": 5,
        "dm_handler":    True,
        "vision":        True,
        "research":      True,
        "price_eur":     349,
        "label":         "€349 / Monat",
    },
}


# ── Settings I/O ──────────────────────────────────────────────────────────────

def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_settings(s: dict):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Merge with existing to avoid wiping other keys (mode, schedules, etc.)
    existing = _load_settings()
    existing.update(s)
    SETTINGS_FILE.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ensure_billing_keys(s: dict) -> dict:
    """Stellt sicher dass alle Billing-Felder vorhanden sind."""
    today = date.today().isoformat()
    trial_expires = (date.today() + timedelta(days=14)).isoformat()
    defaults = {
        "plan":                   "trial",
        "plan_expires":           trial_expires,
        "stripe_customer_id":     "",
        "stripe_subscription_id": "",
        "posts_this_month":       0,
        "month_reset_date":       date.today().replace(day=1).isoformat(),
        "activated_at":           today,
    }
    changed = False
    for k, v in defaults.items():
        if k not in s:
            s[k] = v
            changed = True
    if changed:
        _save_settings(s)
    return s


# ── Public API ────────────────────────────────────────────────────────────────

def get_plan_info() -> dict:
    """
    Gibt Plan-Status zurück:
    {plan, name, expires, days_left, expired, posts_this_month,
     max_posts, posts_left, limits, active}
    """
    s = _ensure_billing_keys(_load_settings())
    plan_key  = s.get("plan", "trial")
    limits    = PLANS.get(plan_key, PLANS["trial"])

    expires_str = s.get("plan_expires", "")
    try:
        expires = date.fromisoformat(expires_str)
        days_left = (expires - date.today()).days
        expired = days_left < 0
    except ValueError:
        expires = date.today() + timedelta(days=14)
        days_left = 14
        expired = False

    # Monatszähler zurücksetzen wenn neuer Monat
    reset_str = s.get("month_reset_date", date.today().replace(day=1).isoformat())
    try:
        reset_date = date.fromisoformat(reset_str)
        current_month_start = date.today().replace(day=1)
        if reset_date < current_month_start:
            s["posts_this_month"] = 0
            s["month_reset_date"] = current_month_start.isoformat()
            _save_settings(s)
    except ValueError:
        pass

    posts_this_month = s.get("posts_this_month", 0)
    max_posts = limits["max_posts"]  # None = unbegrenzt
    posts_left = None if max_posts is None else max(0, max_posts - posts_this_month)

    active = not expired and (plan_key != "trial" or not expired)

    return {
        "plan":            plan_key,
        "name":            limits["name"],
        "label":           limits["label"],
        "expires":         expires.isoformat(),
        "days_left":       days_left,
        "expired":         expired,
        "posts_this_month": posts_this_month,
        "max_posts":       max_posts,
        "posts_left":      posts_left,
        "limits":          limits,
        "active":          active,
        "stripe_customer_id":     s.get("stripe_customer_id", ""),
        "stripe_subscription_id": s.get("stripe_subscription_id", ""),
    }


def can_generate() -> tuple[bool, str]:
    """
    Prüft ob ein Post generiert werden darf.
    Returns: (allowed: bool, reason: str)
    """
    info = get_plan_info()

    if info["expired"]:
        return False, f"Plan abgelaufen ({info['plan']}). Bitte unter /billing upgraden."

    max_posts = info["max_posts"]
    if max_posts is not None and info["posts_this_month"] >= max_posts:
        return False, (
            f"Monatliches Limit erreicht ({max_posts} Posts). "
            f"Upgrade unter /billing."
        )

    return True, ""


def can_use_feature(feature: str) -> bool:
    """
    Prüft ob ein Feature im aktuellen Plan verfügbar ist.
    Features: 'dm_handler', 'vision', 'research'
    """
    info = get_plan_info()
    if info["expired"]:
        return False
    return bool(info["limits"].get(feature, False))


def track_post_generated():
    """Inkrementiert den Post-Zähler nach erfolgreicher Generierung."""
    s = _ensure_billing_keys(_load_settings())
    s["posts_this_month"] = s.get("posts_this_month", 0) + 1
    _save_settings(s)
    log.info(f"[Plan] Post gezählt: {s['posts_this_month']} diesen Monat")


def activate_plan(
    plan: str,
    stripe_customer_id: str = "",
    stripe_subscription_id: str = "",
    expires_date: str = "",          # ISO-Datum z.B. "2026-04-26"
    license_key: str = "",
) -> bool:
    """
    Aktiviert einen Plan. Wird von Stripe-Webhook und License-Key-Route aufgerufen.
    """
    if plan not in PLANS:
        log.error(f"[Plan] Ungültiger Plan: {plan}")
        return False

    if not expires_date:
        expires_date = (date.today() + timedelta(days=31)).isoformat()

    _save_settings({
        "plan":                   plan,
        "plan_expires":           expires_date,
        "stripe_customer_id":     stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "activated_at":           date.today().isoformat(),
    })
    log.info(f"[Plan] Aktiviert: {plan} bis {expires_date} (Stripe: {stripe_subscription_id or license_key})")
    return True


def deactivate_plan(reason: str = ""):
    """Setzt Plan auf Trial zurück (z.B. bei Zahlungsausfall)."""
    expires = (date.today() + timedelta(days=3)).isoformat()  # 3 Tage Gnadenfrist
    _save_settings({
        "plan":         "trial",
        "plan_expires": expires,
    })
    log.warning(f"[Plan] Deaktiviert: {reason}. Gnadenfrist bis {expires}")


# ── License Key Validation ─────────────────────────────────────────────────────

import hashlib, hmac, os as _os

_LICENSE_SECRET = _os.getenv("LICENSE_SECRET", "sozibot-license-2026")

PLAN_KEY_PREFIX = {
    "SZB-S": "starter",
    "SZB-P": "pro",
    "SZB-A": "agency",
}


def validate_license_key(key: str) -> tuple[bool, str]:
    """
    Format: SZB-P-YYYYMM-XXXXXXXX
    Prefix bestimmt Plan, YYYYMM = Ablaufmonat, XXXXXXXX = HMAC-Kurzcode.
    Returns: (valid, plan_key)
    """
    key = key.strip().upper()
    parts = key.split("-")
    if len(parts) != 4:
        return False, ""

    prefix  = f"{parts[0]}-{parts[1]}"
    expiry  = parts[2]   # YYYYMM
    checksum = parts[3]

    plan = PLAN_KEY_PREFIX.get(prefix)
    if not plan:
        return False, ""

    # Ablaufdatum prüfen
    try:
        exp_year  = int(expiry[:4])
        exp_month = int(expiry[4:6])
        exp_date  = date(exp_year, exp_month, 1) + timedelta(days=32)
        exp_date  = exp_date.replace(day=1)  # erster des Folgemonats
        if date.today() >= exp_date:
            return False, ""
    except (ValueError, IndexError):
        return False, ""

    # HMAC prüfen
    payload   = f"{prefix}-{expiry}"
    expected  = hmac.new(
        _LICENSE_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:8].upper()
    if not hmac.compare_digest(checksum, expected):
        return False, ""

    return True, plan


def generate_license_key(plan: str, year: int, month: int) -> str:
    """Generiert einen gültigen License Key (nur intern / Admin-Nutzung)."""
    prefix_map = {"starter": "SZB-S", "pro": "SZB-P", "agency": "SZB-A"}
    prefix  = prefix_map.get(plan, "SZB-S")
    expiry  = f"{year}{month:02d}"
    payload = f"{prefix}-{expiry}"
    checksum = hmac.new(
        _LICENSE_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:8].upper()
    return f"{prefix}-{expiry}-{checksum}"
