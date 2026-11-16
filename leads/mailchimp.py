"""Add newsletter sign-ups to the Mailchimp audience named in Site settings."""

import hashlib
import logging

import requests
from django.conf import settings

from core.models import SiteSettings

from .models import Lead

log = logging.getLogger(__name__)


def sync_newsletter_lead(lead: Lead) -> bool:
    """Best effort: a Mailchimp outage must never lose the lead itself."""
    if lead.intent != Lead.Intent.NEWSLETTER or not lead.consent:
        return False

    api_key = settings.MAILCHIMP_API_KEY
    list_id = SiteSettings.load().mailchimp_list_id
    if not api_key or "-" not in api_key or not list_id:
        return False

    dc = api_key.rsplit("-", 1)[1]
    member_hash = hashlib.md5(lead.email.lower().encode()).hexdigest()
    first, _, last = lead.full_name.partition(" ")
    url = f"https://{dc}.api.mailchimp.com/3.0/lists/{list_id}/members/{member_hash}"

    try:
        # PUT = upsert, so a repeat sign-up doesn't error.
        response = requests.put(
            url,
            auth=("herwell", api_key),
            json={
                "email_address": lead.email,
                "status_if_new": "subscribed",
                "merge_fields": {"FNAME": first, "LNAME": last},
                "tags": [lead.audience],
            },
            timeout=6,
        )
        response.raise_for_status()
    except requests.RequestException:
        log.exception("Mailchimp sync failed for lead %s", lead.pk)
        return False

    Lead.objects.filter(pk=lead.pk).update(mailchimp_synced=True)
    return True
