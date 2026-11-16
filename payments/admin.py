from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.decorators import action, display

from . import paystack
from .models import PricingTier, Transaction, WebhookEvent


@admin.register(PricingTier)
class PricingTierAdmin(ModelAdmin):
    list_display = ("name", "audience", "price", "currency", "interval", "is_highlighted", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("audience", "interval", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "audience", "description")}),
        ("Price", {"fields": ("price", "currency", "interval", "paystack_plan_code")}),
        ("Card on the site", {"fields": ("features", "is_highlighted", "sort_order", "is_active")}),
    )


@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display = ("created_at", "reference", "email", "tier", "amount_display", "status_badge", "channel", "paid_at")
    list_filter = ("status", "currency", "channel", "tier", ("created_at", RangeDateFilter))
    list_filter_submit = True
    search_fields = ("reference", "email", "full_name")
    date_hierarchy = "created_at"
    actions_list = ["check_gateway"]
    readonly_fields = [f.name for f in Transaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # the payment provider is the source of truth

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description="Amount", ordering="amount")
    def amount_display(self, obj):
        return f"{obj.currency} {obj.amount:,.2f}"

    @display(
        description="Status",
        ordering="status",
        label={"Paid": "success", "Pending": "warning", "Failed": "danger", "Abandoned": "info", "Refunded": "info"},
    )
    def status_badge(self, obj):
        return obj.get_status_display()

    @action(description="Test gateway connection", icon="power", url_path="check-gateway")
    def check_gateway(self, request):
        ok, detail = paystack.check_connection()
        messages.add_message(request, messages.SUCCESS if ok else messages.ERROR, detail)
        return redirect(reverse("admin:payments_transaction_changelist"))


@admin.register(WebhookEvent)
class WebhookEventAdmin(ModelAdmin):
    """Developer troubleshooting only. Hidden from the sidebar."""

    list_display = ("received_at", "provider", "event_type", "event_key")
    list_filter = ("provider", "event_type")
    readonly_fields = ("provider", "event_key", "event_type", "payload", "received_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
