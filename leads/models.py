from django.db import models


class Lead(models.Model):
    """One submission from any form on the site (see src/lib/leads.ts in the frontend)."""

    class Intent(models.TextChoices):
        RESOURCE_DOWNLOAD = "resource_download", "Resource download"
        BOOK_DEMO = "book_demo", "Demo request"
        GENERAL_ENQUIRY = "general_enquiry", "Contact message"
        NEWSLETTER = "newsletter", "Newsletter sign-up"

    class Audience(models.TextChoices):
        EMPLOYER = "employer", "Employer"
        INDIVIDUAL = "individual", "Individual"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    intent = models.CharField("Type", max_length=32, choices=Intent.choices, db_index=True)
    audience = models.CharField(max_length=16, choices=Audience.choices, db_index=True)
    full_name = models.CharField("Name", max_length=160, blank=True)  # email-only forms leave it empty
    email = models.EmailField(db_index=True)
    organisation = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=160, blank=True)
    message = models.TextField(blank=True)
    resource = models.CharField("Resource requested", max_length=200, blank=True)
    consent = models.BooleanField("Marketing opt-in", default=False)
    source = models.CharField("Submitted from", max_length=200, blank=True)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    staff_notes = models.TextField(blank=True)
    mailchimp_synced = models.BooleanField(default=False, editable=False)

    created_at = models.DateTimeField("Received", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "form submission"
        verbose_name_plural = "form submissions"

    def __str__(self) -> str:
        return f"{self.get_intent_display()} · {self.full_name or self.email}"
