import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class Audience(models.TextChoices):
    EMPLOYER = "employer", "Employer"
    INDIVIDUAL = "individual", "For You"


class Published(models.Model):
    is_published = models.BooleanField("Show on site", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ── Resources & downloads ─────────────────────────────────────────────────────
class Resource(Published):
    class Icon(models.TextChoices):
        CHECKLIST = "checklist", "Checklist"
        GUIDE = "guide", "Guide"
        TEMPLATE = "template", "Template"
        TRACKER = "tracker", "Tracker"
        CONVERSATION = "conversation", "Conversation"

    title = models.CharField(max_length=160)
    badge = models.CharField(max_length=80, help_text='Small label on the card, e.g. "Free PDF · Self-assessment".')
    description = models.TextField(max_length=400)
    audience = models.CharField(max_length=20, choices=Audience.choices, help_text="Which page shows this download.")
    icon = models.CharField(max_length=20, choices=Icon.choices, default=Icon.GUIDE)
    file = models.FileField(
        "PDF",
        upload_to="resources/",
        blank=True,
        validators=[FileExtensionValidator(["pdf"])],
        help_text="Downloads after the visitor fills in the short form. Leave empty to show the card as “Coming soon”.",
    )
    sort_order = models.PositiveSmallIntegerField("Order", default=0, help_text="Lower numbers show first.")

    class Meta:
        ordering = ("audience", "sort_order", "title")
        verbose_name = "resource"

    def __str__(self) -> str:
        return self.title


# ── Videos ────────────────────────────────────────────────────────────────────
YOUTUBE_ID = re.compile(r"(?:youtu\.be/|v=|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{11})")


def youtube_id_from(url: str) -> str | None:
    match = YOUTUBE_ID.search(url or "")
    return match.group(1) if match else None


class Video(Published):
    class Placement(models.TextChoices):
        HOME = "home", "Home page"
        EMPLOYER = "employer", "Employer page"
        INDIVIDUAL = "individual", "For You page"

    placement = models.CharField(
        "Shows on",
        max_length=20,
        choices=Placement.choices,
        unique=True,
        help_text="Each page has one founder video.",
    )
    youtube_url = models.URLField("YouTube link", help_text="Paste the normal YouTube address of the video.")
    title = models.CharField(max_length=200, help_text="The video's own title, read out by screen readers.")
    duration = models.CharField(max_length=8, blank=True, help_text="Runtime as mm:ss, e.g. 45:21. Optional.")
    eyebrow = models.CharField("Small label", max_length=120, blank=True)
    heading = models.CharField(max_length=160)
    blurb = models.TextField(max_length=600)

    class Meta:
        ordering = ("placement",)

    def __str__(self) -> str:
        return f"{self.get_placement_display()}: {self.heading}"

    @property
    def youtube_id(self) -> str | None:
        return youtube_id_from(self.youtube_url)

    def clean(self):
        if self.youtube_url and not self.youtube_id:
            raise ValidationError({"youtube_url": "That doesn't look like a YouTube video link."})
        if self.duration and not re.fullmatch(r"\d{1,3}:[0-5]\d", self.duration):
            raise ValidationError({"duration": "Use mm:ss, for example 45:21."})


# ── Events & webinars ─────────────────────────────────────────────────────────
class EventQuerySet(models.QuerySet):
    def upcoming(self):
        return self.filter(starts_at__gte=timezone.now()).order_by("starts_at")

    def past(self):
        return self.filter(starts_at__lt=timezone.now()).order_by("-starts_at")


class Event(Published):
    class Type(models.TextChoices):
        WEBINAR = "webinar", "Webinar"
        QA = "qa", "Q&A"
        WORKSHOP = "workshop", "Workshop"

    title = models.CharField(max_length=200)
    event_type = models.CharField("Type", max_length=20, choices=Type.choices, default=Type.WEBINAR)
    starts_at = models.DateTimeField(
        "Date & time",
        help_text="Events move from “Upcoming” to “Past” on their own once this time passes.",
    )
    speaker = models.CharField(max_length=120)
    registration_url = models.URLField(
        "Registration link", blank=True, help_text="Zoom, Eventbrite, Google Form, … Optional for past events."
    )
    recording_url = models.URLField("Recording link", blank=True, help_text="Optional. Shown on past events.")

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ("-starts_at",)

    def __str__(self) -> str:
        return self.title

    @property
    def is_upcoming(self) -> bool:
        return self.starts_at >= timezone.now()
