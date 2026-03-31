"""
Billing Routes — Stripe Checkout, Webhook, License Key Aktivierung.

Umgebungsvariablen (.env):
  STRIPE_SECRET_KEY        sk_live_... oder sk_test_...
  STRIPE_WEBHOOK_SECRET    whsec_...
  STRIPE_PRICE_STARTER     price_...
  STRIPE_PRICE_PRO         price_...
  STRIPE_PRICE_AGENCY      price_...
  LICENSE_SECRET           (geheimes Wort für Key-Generierung)
  APP_BASE_URL             https://deinedomain.de  (für Stripe Redirect)
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import date, timedelta

from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from dashboard.services.plan_service import (
    PLANS,
    activate_plan,
    deactivate_plan,
    generate_license_key,
    get_plan_info,
    track_post_generated,
    validate_license_key,
)

log = logging.getLogger(__name__)
bp  = Blueprint("billing", __name__, url_prefix="/billing")

# Stripe Plan → Price ID Mapping (aus .env)
_PRICE_IDS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER", ""),
    "pro":     os.getenv("STRIPE_PRICE_PRO",     ""),
    "agency":  os.getenv("STRIPE_PRICE_AGENCY",  ""),
}

_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5000")


def _stripe():
    """Gibt den Stripe-Client zurück (lazy import)."""
    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        return stripe
    except ImportError:
        return None


# ── Billing Übersicht ─────────────────────────────────────────────────────────

@bp.route("/")
def billing_overview():
    info = get_plan_info()
    stripe_ok = bool(os.getenv("STRIPE_SECRET_KEY"))
    return render_template(
        "billing.html",
        plan_info=info,
        plans=PLANS,
        stripe_ok=stripe_ok,
        price_ids=_PRICE_IDS,
    )


# ── Stripe Checkout ───────────────────────────────────────────────────────────

@bp.route("/checkout/<plan_key>")
def checkout(plan_key: str):
    """Leitet zu Stripe Checkout weiter."""
    if plan_key not in PLANS or plan_key == "trial":
        return redirect(url_for("billing.billing_overview"))

    stripe = _stripe()
    if not stripe or not stripe.api_key or "sk_" not in stripe.api_key:
        # Kein Stripe konfiguriert — direkt zu License Key
        return redirect(url_for("billing.billing_overview") + "?no_stripe=1")

    price_id = _PRICE_IDS.get(plan_key)
    if not price_id:
        return redirect(url_for("billing.billing_overview") + "?no_price=1")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=_BASE_URL + "/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=_BASE_URL + "/billing/?canceled=1",
            metadata={"plan": plan_key},
        )
        return redirect(session.url, code=303)
    except Exception as e:
        log.error(f"[Billing] Stripe Checkout Fehler: {e}")
        return redirect(url_for("billing.billing_overview") + "?stripe_error=1")


@bp.route("/success")
def checkout_success():
    """Nach erfolgreicher Zahlung — Plan wird via Webhook aktiviert."""
    return redirect(url_for("billing.billing_overview") + "?success=1")


# ── Stripe Webhook ────────────────────────────────────────────────────────────

@bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """
    Empfängt Stripe-Events und aktualisiert den Plan.
    Muss in Stripe Dashboard als Endpoint eingetragen sein.
    """
    payload    = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    secret     = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    stripe = _stripe()
    if not stripe:
        return jsonify({"error": "stripe not installed"}), 500

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError:
        log.warning("[Billing] Ungültige Stripe Webhook Signatur")
        return jsonify({"error": "invalid signature"}), 400
    except Exception as e:
        log.error(f"[Billing] Webhook Parse-Fehler: {e}")
        return jsonify({"error": str(e)}), 400

    etype = event["type"]
    data  = event["data"]["object"]

    if etype == "checkout.session.completed":
        # Neue Subscription nach Checkout
        plan            = data.get("metadata", {}).get("plan", "starter")
        customer_id     = data.get("customer", "")
        subscription_id = data.get("subscription", "")
        expires         = (date.today() + timedelta(days=31)).isoformat()
        activate_plan(plan, customer_id, subscription_id, expires)
        log.info(f"[Billing] Checkout abgeschlossen: {plan} für {customer_id}")

    elif etype in ("invoice.paid", "invoice.payment_succeeded"):
        # Monatliche Erneuerung — Plan verlängern
        subscription_id = data.get("subscription", "")
        customer_id     = data.get("customer", "")
        expires         = (date.today() + timedelta(days=31)).isoformat()
        # Plan beibehalten, nur Datum verlängern
        info = get_plan_info()
        activate_plan(info["plan"], customer_id, subscription_id, expires)
        log.info(f"[Billing] Rechnung bezahlt — Plan verlängert bis {expires}")

    elif etype in ("invoice.payment_failed", "customer.subscription.deleted"):
        # Zahlung fehlgeschlagen oder Abo gekündigt
        reason = "Zahlung fehlgeschlagen" if "failed" in etype else "Abo gekündigt"
        deactivate_plan(reason)
        log.warning(f"[Billing] {reason} — Plan deaktiviert")

    return jsonify({"ok": True})


# ── License Key Aktivierung ───────────────────────────────────────────────────

@bp.route("/activate", methods=["POST"])
def activate_license():
    """Aktiviert einen Plan per License Key (ohne Stripe)."""
    data = request.get_json(silent=True) or {}
    key  = data.get("key", "").strip()

    if not key:
        return jsonify({"ok": False, "error": "Kein Key angegeben"}), 400

    valid, plan = validate_license_key(key)
    if not valid:
        return jsonify({"ok": False, "error": "Ungültiger oder abgelaufener License Key"}), 400

    expires = (date.today() + timedelta(days=31)).isoformat()
    activate_plan(plan, license_key=key, expires_date=expires)

    return jsonify({
        "ok":    True,
        "plan":  plan,
        "name":  PLANS[plan]["name"],
        "expires": expires,
    })


# ── Admin: License Key generieren (nur intern) ────────────────────────────────

@bp.route("/admin/generate-key", methods=["POST"])
def admin_generate_key():
    """
    Generiert einen License Key. Nur mit ADMIN_SECRET absicherbar.
    POST { "plan": "pro", "year": 2026, "month": 5, "admin_secret": "..." }
    """
    admin_secret = os.getenv("ADMIN_SECRET", "")
    data = request.get_json(silent=True) or {}

    if not admin_secret or data.get("admin_secret") != admin_secret:
        return jsonify({"error": "Nicht autorisiert"}), 403

    plan  = data.get("plan", "starter")
    year  = int(data.get("year",  date.today().year))
    month = int(data.get("month", date.today().month + 1))

    key = generate_license_key(plan, year, month)
    return jsonify({"key": key, "plan": plan, "expires": f"{year}-{month:02d}"})


# ── Plan-Info API ─────────────────────────────────────────────────────────────

@bp.route("/status")
def plan_status():
    """JSON-Endpunkt für Plan-Status (für Dashboard-Widgets)."""
    return jsonify(get_plan_info())
