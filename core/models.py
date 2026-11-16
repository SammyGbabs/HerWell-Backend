from django.db import models


class SingletonModel(models.Model):
    """A table that only ever holds one row (pk=1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Deleting the only settings row would blank the live site; refuse.
        return (0, {})

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SiteSettings(SingletonModel):
    """Values that used to be hardcoded across the React app."""

    # Contact
    contact_email = models.EmailField(default="info@herwellafrica.com")
    whatsapp_community_url = models.URLField(
        "WhatsApp community link", blank=True, default="https://chat.whatsapp.com"
    )

    # Social
    linkedin_url = models.URLField("LinkedIn", blank=True)
    instagram_url = models.URLField("Instagram", blank=True)
    facebook_url = models.URLField("Facebook", blank=True)
    x_url = models.URLField("X (Twitter)", blank=True)
    youtube_url = models.URLField("YouTube channel", blank=True)
    tiktok_url = models.URLField("TikTok", blank=True)

    # Blog & newsletter
    substack_url = models.URLField(
        "Substack URL",
        blank=True,
        help_text="Your publication's address, e.g. https://herwell.substack.com. "
        "The site reads the feed from here.",
    )
    mailchimp_list_id = models.CharField(
        "Mailchimp audience (list) ID",
        max_length=64,
        blank=True,
        help_text="Newsletter sign-ups are added to this audience. "
        "Found in Mailchimp under Audience → Settings → Audience name and defaults.",
    )

    # Bookkeeping for the "Refresh blog now" button
    blog_last_refresh_at = models.DateTimeField("Blog last refreshed", null=True, blank=True, editable=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self) -> str:
        return "Site settings"
