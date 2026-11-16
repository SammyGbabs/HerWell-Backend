import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.decorators import action, display

from .models import Lead

CSV_COLUMNS = (
    ("created_at", "Received"),
    ("intent", "Type"),
    ("audience", "Audience"),
    ("full_name", "Name"),
    ("email", "Email"),
    ("organisation", "Organisation"),
    ("role", "Role"),
    ("resource", "Resource"),
    ("message", "Message"),
    ("consent", "Marketing opt-in"),
    ("source", "Submitted from"),
    ("status", "Status"),
    ("staff_notes", "Staff notes"),
)


def _csv_safe(value) -> str:
    """Stop spreadsheet formula injection from visitor-typed text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = ("created_at", "intent_badge", "full_name", "email", "organisation", "audience", "resource", "status")
    list_display_links = ("created_at", "full_name")
    list_editable = ("status",)
    list_filter = (
        "intent",
        "audience",
        "status",
        "consent",
        ("created_at", RangeDateFilter),
    )
    list_filter_submit = True
    search_fields = ("full_name", "email", "organisation", "message", "resource")
    date_hierarchy = "created_at"
    actions = ["export_csv", "mark_done"]
    list_per_page = 50

    readonly_fields = (
        "intent", "audience", "full_name", "email", "organisation", "role", "message",
        "resource", "consent", "source", "mailchimp_synced", "created_at",
    )
    fieldsets = (
        ("Submission", {"fields": ("created_at", "intent", "audience", "source")}),
        ("Person", {"fields": ("full_name", "email", "organisation", "role")}),
        ("What they sent", {"fields": ("message", "resource", "consent", "mailchimp_synced")}),
        ("Follow-up", {"fields": ("status", "staff_notes")}),
    )

    def has_add_permission(self, request):
        return False  # submissions only come from the website

    @display(
        description="Type",
        label={
            "Resource download": "info",
            "Demo request": "success",
            "Contact message": "warning",
            "Newsletter sign-up": "primary",
        },
    )
    def intent_badge(self, obj):
        return obj.get_intent_display()

    @action(description="Export selected to CSV", icon="download")
    def export_csv(self, request, queryset):
        stamp = timezone.localtime().strftime("%Y-%m-%d")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="herwell-submissions-{stamp}.csv"'
        response.write("﻿")  # BOM so Excel reads accents correctly

        writer = csv.writer(response)
        writer.writerow([label for _, label in CSV_COLUMNS])
        for lead in queryset.iterator():
            row = []
            for field, _ in CSV_COLUMNS:
                value = getattr(lead, field)
                if field == "created_at":
                    value = timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
                elif field in ("intent", "audience", "status"):
                    value = getattr(lead, f"get_{field}_display")()
                elif field == "consent":
                    value = "Yes" if value else "No"
                row.append(_csv_safe(value))
            writer.writerow(row)
        return response

    @action(description="Mark selected as done", icon="done_all")
    def mark_done(self, request, queryset):
        updated = queryset.update(status=Lead.Status.DONE)
        self.message_user(request, f"{updated} submission(s) marked done.")
