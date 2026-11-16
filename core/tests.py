"""End-to-end checks for the public API, the payment webhook and the admin screens."""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from content.models import Event, Resource, Video
from core.models import SiteSettings
from leads.models import Lead
from payments.models import PricingTier, Transaction, WebhookEvent

SECRET = "sk_test_abc123"


def lead_payload(**overrides):
    payload = {
        "intent": "resource_download",
        "audience": "individual",
        "fullName": "Wanjiru Kamau",
        "email": "wanjiru@example.com",
        "resource": "Menopause Myths, Answered",
        "consent": True,
        "source": "individuals/free-resources",
    }
    payload.update(overrides)
    return payload


class PublicApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True})

    def test_settings_hides_empty_socials(self):
        s = SiteSettings.load()
        s.linkedin_url = "https://linkedin.com/company/herwell"
        s.save()
        data = self.client.get("/api/settings/").json()
        self.assertEqual(data["social"], {"linkedin": "https://linkedin.com/company/herwell"})
        self.assertEqual(data["contactEmail"], "info@herwellafrica.com")

    def test_lead_matches_frontend_contract(self):
        response = self.client.post("/api/leads/", lead_payload(), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get(pk=response.json()["id"])
        self.assertEqual(lead.full_name, "Wanjiru Kamau")
        self.assertEqual(lead.status, Lead.Status.NEW)

    def test_lead_honeypot_stores_nothing(self):
        response = self.client.post("/api/leads/", lead_payload(website="spam.biz"), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Lead.objects.exists())

    def test_newsletter_needs_only_email(self):
        response = self.client.post("/api/leads/", lead_payload(intent="newsletter", fullName=""),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_contact_message_needs_name(self):
        response = self.client.post("/api/leads/", lead_payload(intent="general_enquiry", fullName=""),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_employer_demo_needs_organisation(self):
        response = self.client.post(
            "/api/leads/", lead_payload(intent="book_demo", audience="employer"), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_resources_filter_by_audience_and_hide_unpublished(self):
        Resource.objects.create(title="A", badge="b", description="d", audience="employer")
        Resource.objects.create(title="B", badge="b", description="d", audience="individual")
        Resource.objects.create(title="C", badge="b", description="d", audience="employer", is_published=False)
        titles = [r["title"] for r in self.client.get("/api/resources/?audience=employer").json()]
        self.assertEqual(titles, ["A"])

    def test_events_sort_themselves(self):
        now = timezone.now()
        Event.objects.create(title="Soon", starts_at=now + timedelta(days=1), speaker="x")
        Event.objects.create(title="Later", starts_at=now + timedelta(days=9), speaker="x")
        Event.objects.create(title="Done", starts_at=now - timedelta(days=1), speaker="x")
        data = self.client.get("/api/events/").json()
        self.assertEqual([e["title"] for e in data["upcoming"]], ["Soon", "Later"])
        self.assertEqual([e["title"] for e in data["past"]], ["Done"])

    def test_video_youtube_id_extracted(self):
        Video.objects.create(placement="home", youtube_url="https://youtu.be/ZRs2SRSvNT0",
                             title="t", heading="h", blurb="b")
        self.assertEqual(self.client.get("/api/videos/").json()["home"]["youtubeId"], "ZRs2SRSvNT0")


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class PaystackWebhookTests(TestCase):
    url = "/api/payments/paystack/webhook/"

    def setUp(self):
        self.tier = PricingTier.objects.create(name="Essential", slug="essential", price=Decimal("1500.00"), currency="KES")
        self.tx = Transaction.objects.create(reference="hw_ref1", tier=self.tier, email="a@b.co",
                                             amount=self.tier.price, currency="KES")

    def post(self, body: dict, secret: str = SECRET):
        raw = json.dumps(body).encode()
        sig = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
        return self.client.post(self.url, raw, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig)

    def verified(self, **overrides):
        data = {"reference": "hw_ref1", "status": "success", "amount": 150000, "currency": "KES",
                "channel": "mobile_money", "paid_at": "2026-11-12T10:00:00Z",
                "authorization": {"authorization_code": "AUTH_secret", "last4": "4081", "card_type": "visa"}}
        data.update(overrides)
        return data

    def test_bad_signature_rejected(self):
        response = self.post({"event": "charge.success", "data": {"id": 1, "reference": "hw_ref1"}}, secret="wrong")
        self.assertEqual(response.status_code, 401)

    def test_success_is_reverified_and_idempotent(self):
        event = {"event": "charge.success", "data": {"id": 99, "reference": "hw_ref1"}}
        with mock.patch("payments.paystack.verify", return_value=self.verified()) as verify:
            self.assertEqual(self.post(event).status_code, 200)
            self.assertEqual(self.post(event).status_code, 200)  # retry
        self.assertEqual(verify.call_count, 1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.Status.SUCCESS)
        self.assertEqual(self.tx.card_last4, "4081")
        self.assertNotIn("AUTH_secret", json.dumps(self.tx.provider_payload))
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_underpayment_is_not_marked_paid(self):
        event = {"event": "charge.success", "data": {"id": 100, "reference": "hw_ref1"}}
        with mock.patch("payments.paystack.verify", return_value=self.verified(amount=100)):
            self.post(event)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.Status.FAILED)

    def test_checkout_creates_pending_transaction(self):
        with mock.patch("payments.paystack.initialize", return_value="https://checkout.paystack.com/x"):
            response = self.client.post("/api/checkout/", {"tier": "essential", "email": "c@d.co"},
                                        content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["url"], "https://checkout.paystack.com/x")
        self.assertTrue(Transaction.objects.filter(reference=response.json()["reference"], status="pending").exists())


class AdminScreensTests(TestCase):
    """Every screen the client will click must render."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "a-strong-pass-123")
        self.client.force_login(self.admin)
        Lead.objects.create(intent="newsletter", audience="individual", full_name="=cmd|' /C calc'!A0",
                            email="x@y.co")
        Event.objects.create(title="E", starts_at=timezone.now(), speaker="s")
        Resource.objects.create(title="R", badge="b", description="d", audience="employer")
        Video.objects.create(placement="home", youtube_url="https://youtu.be/ZRs2SRSvNT0",
                             title="t", heading="h", blurb="b")
        tier = PricingTier.objects.create(name="T", slug="t", price=Decimal("10"))
        Transaction.objects.create(reference="r", tier=tier, email="e@e.co", amount=10, currency="KES")

    def test_changelists_and_forms_render(self):
        for model in ("content_resource", "content_video", "content_event", "leads_lead",
                      "payments_pricingtier", "payments_transaction", "payments_webhookevent",
                      "auth_user", "auth_group"):
            response = self.client.get(reverse(f"admin:{model}_changelist"))
            self.assertEqual(response.status_code, 200, model)
        for model in ("content_resource", "content_video", "content_event", "payments_pricingtier"):
            self.assertEqual(self.client.get(reverse(f"admin:{model}_add")).status_code, 200, model)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_settings_opens_single_row(self):
        response = self.client.get(reverse("admin:core_sitesettings_changelist"))
        self.assertRedirects(response, reverse("admin:core_sitesettings_change", args=(1,)))
        self.assertContains(self.client.get(response.url), "Refresh blog now")

    @override_settings(VERCEL_DEPLOY_HOOK_URL="https://api.vercel.com/v1/integrations/deploy/x")
    def test_refresh_blog_calls_deploy_hook(self):
        SiteSettings.load()
        with mock.patch("core.admin.requests.post") as post:
            self.client.get(reverse("admin:core_sitesettings_refresh_blog", args=(1,)))
        post.assert_called_once()
        self.assertIsNotNone(SiteSettings.load().blog_last_refresh_at)

    @override_settings(PAYSTACK_SECRET_KEY="")
    def test_gateway_check_without_key(self):
        response = self.client.get(reverse("admin:payments_transaction_check_gateway"), follow=True)
        self.assertContains(response, "No Paystack secret key configured")

    def test_csv_export_neutralises_formulas(self):
        response = self.client.post(reverse("admin:leads_lead_changelist"), {
            "action": "export_csv", "_selected_action": list(Lead.objects.values_list("pk", flat=True)),
        })
        body = response.content.decode("utf-8-sig")
        self.assertIn("'=cmd", body)
