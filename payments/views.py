import json
import logging
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import paystack
from .models import PricingTier, Transaction, WebhookEvent
from .serializers import CheckoutSerializer, PricingTierSerializer

log = logging.getLogger(__name__)


class PricingListView(APIView):
    """GET /api/pricing/?audience=individual|employer"""

    def get(self, request):
        qs = PricingTier.objects.filter(is_active=True)
        if audience := request.query_params.get("audience"):
            qs = qs.filter(audience=audience)
        return Response(PricingTierSerializer(qs, many=True).data, headers={"Cache-Control": "public, max-age=60"})


class CheckoutView(APIView):
    """POST /api/checkout/ { tier, email, fullName? } → { url, reference }"""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tier: PricingTier = serializer.validated_data["tier"]
        email = serializer.validated_data["email"]

        reference = f"hw_{uuid.uuid4().hex[:20]}"
        tx = Transaction.objects.create(
            reference=reference,
            tier=tier,
            email=email,
            full_name=serializer.validated_data.get("fullName", ""),
            amount=tier.price,
            currency=tier.currency,
        )
        try:
            url = paystack.initialize(
                email=email,
                amount_minor=tier.amount_minor,
                currency=tier.currency,
                reference=reference,
                plan=tier.paystack_plan_code,
                metadata={"tier": tier.slug},
            )
        except paystack.PaystackError:
            log.exception("Paystack initialize failed for %s", reference)
            tx.status = Transaction.Status.FAILED
            tx.save(update_fields=["status", "updated_at"])
            return Response(
                {"error": "Payments are unavailable right now. Please try again shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"url": url, "reference": reference}, status=status.HTTP_201_CREATED)


class CheckoutStatusView(APIView):
    """GET /api/checkout/status/?reference=… for the 'thank you' page the buyer returns to."""

    def get(self, request):
        reference = request.query_params.get("reference", "")
        tx = Transaction.objects.filter(reference=reference).first()
        if not tx:
            return Response({"status": "unknown"}, status=status.HTTP_404_NOT_FOUND)
        if tx.status == Transaction.Status.PENDING:
            # The webhook may not have arrived yet (e.g. the server was asleep). Ask Paystack.
            try:
                apply_verified_charge(paystack.verify(reference))
                tx.refresh_from_db()
            except paystack.PaystackError:
                pass
        return Response({"status": tx.status})


def _safe_payload(data: dict) -> dict:
    """Keep the receipt, drop anything that could be reused to charge the customer."""
    data = dict(data)
    auth = data.pop("authorization", None) or {}
    data["authorization"] = {k: auth.get(k) for k in ("channel", "card_type", "last4", "bank", "country_code")}
    data.pop("customer", None)
    return data


def apply_verified_charge(data: dict) -> None:
    """Record a charge that Paystack's verify endpoint has confirmed."""
    reference = data.get("reference")
    if not reference:
        return
    paystack_status = data.get("status")
    auth = data.get("authorization") or {}

    with transaction.atomic():
        tx = Transaction.objects.select_for_update().filter(reference=reference).first()
        if tx is None:
            # Subscription renewals arrive with references we didn't create.
            plan_code = (data.get("plan") or {}).get("plan_code") if isinstance(data.get("plan"), dict) else data.get("plan")
            tier = PricingTier.objects.filter(paystack_plan_code=plan_code).first() if plan_code else None
            tx = Transaction(
                reference=reference,
                tier=tier,
                email=(data.get("customer") or {}).get("email", ""),
                amount=Decimal(int(data.get("amount", 0))) / 100,
                currency=data.get("currency", ""),
            )
        elif paystack_status == "success" and (
            int(data.get("amount", 0)) < int(tx.amount * 100) or data.get("currency") != tx.currency
        ):
            # Compare with what was quoted at checkout, not today's price.
            log.error("Amount/currency mismatch on %s: paid %s %s, expected %s %s", reference,
                      data.get("currency"), data.get("amount"), tx.currency, int(tx.amount * 100))
            tx.status = Transaction.Status.FAILED
            tx.provider_payload = _safe_payload(data)
            tx.save()
            return

        if tx.status in (Transaction.Status.SUCCESS, Transaction.Status.REFUNDED) and tx.pk:
            return  # already final

        status_map = {
            "success": Transaction.Status.SUCCESS,
            "failed": Transaction.Status.FAILED,
            "abandoned": Transaction.Status.ABANDONED,
        }
        tx.status = status_map.get(paystack_status, tx.status)
        tx.channel = data.get("channel", "") or tx.channel
        tx.card_brand = (auth.get("card_type") or auth.get("brand") or "").strip()[:40]
        tx.card_last4 = (auth.get("last4") or "")[:4]
        if tx.status == Transaction.Status.SUCCESS:
            tx.paid_at = parse_datetime(data.get("paid_at") or "") or timezone.now()
        tx.provider_payload = _safe_payload(data)
        tx.save()


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(View):
    """
    POST /api/payments/paystack/webhook/

    1. Reject anything without a valid HMAC signature.
    2. Store the event once (unique key), so Paystack's retries are harmless.
    3. Re-verify the charge with Paystack before marking anything as paid.
    Always answer 200 quickly once the signature is good, or Paystack keeps retrying.
    """

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not paystack.signature_is_valid(request.body, signature):
            return HttpResponse(status=401)

        try:
            event = json.loads(request.body)
        except ValueError:
            return HttpResponse(status=400)

        event_type = event.get("event", "")
        data = event.get("data") or {}
        key = f"{event_type}:{data.get('id') or data.get('reference') or data.get('transaction_reference')}"

        try:
            with transaction.atomic():
                WebhookEvent.objects.create(provider="paystack", event_key=key, event_type=event_type,
                                            payload={"event": event_type, "reference": data.get("reference")})
        except IntegrityError:
            return HttpResponse(status=200)  # duplicate delivery

        try:
            if event_type == "charge.success":
                apply_verified_charge(paystack.verify(data["reference"]))
            elif event_type == "refund.processed":
                Transaction.objects.filter(reference=data.get("transaction_reference")).update(
                    status=Transaction.Status.REFUNDED, updated_at=timezone.now()
                )
        except (paystack.PaystackError, KeyError):
            log.exception("Webhook %s could not be processed", key)
            # Let Paystack retry: remove our marker and report failure.
            WebhookEvent.objects.filter(provider="paystack", event_key=key).delete()
            return HttpResponse(status=500)

        return HttpResponse(status=200)
