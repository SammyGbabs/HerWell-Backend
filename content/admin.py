from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import Event, Resource, Video


@admin.register(Resource)
class ResourceAdmin(ModelAdmin):
    list_display = ("title", "audience", "badge", "has_file", "sort_order", "is_published")
    list_editable = ("sort_order", "is_published")
    list_filter = ("audience", "is_published")
    search_fields = ("title", "description", "badge")
    fieldsets = (
        (None, {"fields": ("title", "badge", "description", "audience", "icon")}),
        ("File", {"fields": ("file",)}),
        ("Display", {"fields": ("sort_order", "is_published")}),
    )

    @display(description="PDF", boolean=True)
    def has_file(self, obj):
        return bool(obj.file)


@admin.register(Video)
class VideoAdmin(ModelAdmin):
    list_display = ("placement", "heading", "duration", "preview", "is_published")
    list_filter = ("placement", "is_published")
    fieldsets = (
        (None, {"fields": ("placement", "youtube_url", "title", "duration")}),
        ("Text beside the video", {"fields": ("eyebrow", "heading", "blurb")}),
        ("Display", {"fields": ("is_published",)}),
    )

    @display(description="YouTube")
    def preview(self, obj):
        if not obj.youtube_id:
            return "-"
        return format_html('<a href="https://youtu.be/{}" target="_blank" rel="noopener">Open ↗</a>', obj.youtube_id)


class WhenFilter(admin.SimpleListFilter):
    title = "when"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return (("upcoming", "Upcoming"), ("past", "Past"))

    def queryset(self, request, queryset):
        if self.value() == "upcoming":
            return queryset.upcoming()
        if self.value() == "past":
            return queryset.past()
        return queryset


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ("title", "event_type", "starts_at", "speaker", "status", "is_published")
    list_filter = (WhenFilter, "event_type", "is_published")
    search_fields = ("title", "speaker")
    date_hierarchy = "starts_at"
    fieldsets = (
        (None, {"fields": ("title", "event_type", "starts_at", "speaker")}),
        ("Links", {"fields": ("registration_url", "recording_url")}),
        ("Display", {"fields": ("is_published",)}),
    )

    @display(description="Status", label={"Upcoming": "success", "Past": "info"})
    def status(self, obj):
        return "Upcoming" if obj.starts_at >= timezone.now() else "Past"
