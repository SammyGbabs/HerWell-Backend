from decimal import Decimal

from django.db import models


class Currency(models.TextChoices):
    KES = "KES", "KES · Kenyan shilling"
    NGN = "NGN", "NGN · Nigerian naira"
    GHS = "GHS", "GHS · Ghanaian cedi"
    ZAR = "ZAR", "ZAR · South African rand"
    USD = "USD", "USD · US dollar"


class PricingTier(models.Model):
    class Interval(models.TextChoices):
        ONE_TIME = "one_time", "One-off payment"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    class Audience(models.TextChoices):
        INDIVIDUAL = "individual", "For You"
        EMPLOYER = "employer", "Employer"

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True, help_text="Short id the website uses, e.g. essential-monthly. Don't change once live.")
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.INDIVIDUAL)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.KES)
    interval = models.CharField("Billing", max_length=20, choices=Interval.choices, default=Interval.MONTHLY)
    description = models.CharField(max_length=240, blank=True)
    features = models.TextField(blank=True, help_text="One feature per line.")
    is_highlighted = models.BooleanField("Highlight as recommended", default=False)
    paystack_plan_code = models.CharField(
        "Paystack plan code",
        max_length=64,
        blank=True,
        help_text="Needed for monthly/yearly tiers: create the plan in the Paystack dashboard and paste its "
        "PLN_… code here. Leave empty for one-off payments.",
    )
    is_active = models.BooleanField("On sale", default=True)
    sort_order = models.PositiveSmallIntegerField("Order", default=0)

    class Meta:
        ordering = ("audience", "sort_order", "price")
        verbose_name = "pricing tier"

    def __str__(self) -> str:
        return f"{self.name} · {self.currency} {self.price}"

    @property
    def amount_minor(self) -> int:
        """Paystack wants the smallest unit (cents, kobo, …)."""
        return int((self.price * Decimal(100)).quantize(Decimal(1)))

    @property
    def feature_list(self) -> list[str]:
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class Transaction(models.Model):
    """Written by checkout and the payment webhook. Read-only in the admin."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Paid"
        FAILED = "failed", "Failed"
        ABANDONED = "abandoned", "Abandoned"
        REFUNDED = "refunded", "Refunded"

    reference = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=20, default="paystack")
    tier = models.ForeignKey(PricingTier, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")
    email = models.EmailField(db_index=True)
    full_name = models.CharField(max_length=160, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    channel = models.CharField(max_length=40, blank=True, help_text="card, mobile_money, bank, …")
    # Only display details. Never the card number, never Paystack's reusable authorization code.
    card_brand = models.CharField(max_length=40, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.reference


class WebhookEvent(models.Model):
    """Paystack retries webhooks. A unique key per event makes processing idempotent."""

    provider = models.CharField(max_length=20)
    event_key = models.CharField(max_length=160)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)
        constraints = [models.UniqueConstraint(fields=("provider", "event_key"), name="unique_webhook_event")]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_type}"
