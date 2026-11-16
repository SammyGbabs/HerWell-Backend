"""
Paystack adapter. Hosted checkout only: the card form lives on Paystack's page,
so no card data ever touches this server.

If the HerWell entity ends up needing Stripe or Flutterwave instead, add a
sibling module with the same four functions and switch `provider` in views.py.
"""

import hashlib
import hmac

import requests
from django.conf import settings

API = "https://api.paystack.co"
TIMEOUT = 15


class PaystackError(Exception):
    pass


def _headers() -> dict[str, str]:
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured.")
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}


def _call(method: str, path: str, **kwargs) -> dict:
    try:
        response = requests.request(method, f"{API}{path}", headers=_headers(), timeout=TIMEOUT, **kwargs)
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackError(f"Could not reach Paystack: {exc}") from exc
    if not response.ok or not body.get("status"):
        raise PaystackError(body.get("message") or f"Paystack returned HTTP {response.status_code}")
    return body.get("data") or {}


def initialize(*, email: str, amount_minor: int, currency: str, reference: str,
               plan: str = "", metadata: dict | None = None) -> str:
    """Start a hosted checkout. Returns the URL to send the buyer to."""
    payload = {
        "email": email,
        "amount": amount_minor,
        "currency": currency,
        "reference": reference,
        "metadata": metadata or {},
    }
    if plan:
        payload["plan"] = plan  # Paystack turns this into a subscription
    if settings.PAYSTACK_CALLBACK_URL:
        payload["callback_url"] = settings.PAYSTACK_CALLBACK_URL
    return _call("POST", "/transaction/initialize", json=payload)["authorization_url"]


def verify(reference: str) -> dict:
    """Ask Paystack directly. Never trust a webhook body on its own for money."""
    return _call("GET", f"/transaction/verify/{reference}")


def signature_is_valid(raw_body: bytes, signature: str) -> bool:
    secret = settings.PAYSTACK_SECRET_KEY
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


def check_connection() -> tuple[bool, str]:
    """Used by the admin's 'Test gateway connection' button."""
    key = settings.PAYSTACK_SECRET_KEY
    if not key:
        return False, "No Paystack secret key configured on the server."
    mode = "LIVE" if key.startswith("sk_live_") else "TEST" if key.startswith("sk_test_") else "unknown"
    try:
        _call("GET", "/transaction", params={"perPage": 1})
    except PaystackError as exc:
        return False, f"Paystack rejected the connection ({mode} key): {exc}"
    return True, f"Connected to Paystack in {mode} mode."
