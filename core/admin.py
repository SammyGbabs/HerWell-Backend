import logging

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import SiteSettings

log = logging.getLogger(__name__)


class SingletonAdmin(ModelAdmin):
    """Skip the list page: the sidebar link opens the one settings row."""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        self.model.load()
        return redirect(reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_change", args=(1,)))


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdmin):
    actions_detail = ["refresh_blog"]
    readonly_fields = ("blog_last_refresh_at", "updated_at")
    fieldsets = (
        ("Contact", {"fields": ("contact_email", "whatsapp_community_url")}),
        (
            "Social links",
            {
                "description": "Leave a field empty to hide that icon on the site.",
                "fields": ("linkedin_url", "instagram_url", "facebook_url", "x_url", "youtube_url", "tiktok_url"),
            },
        ),
        (
            "Blog & newsletter",
            {
                "description": "Posts are written on Substack. The site checks for new posts "
                "automatically every day. Use <b>Refresh blog now</b> (top right) to publish "
                "a new post straight away. It goes live about two minutes later.",
                "fields": ("substack_url", "blog_last_refresh_at", "mailchimp_list_id"),
            },
        ),
        ("History", {"fields": ("updated_at",)}),
    )

    @action(description="Refresh blog now", url_path="refresh-blog", icon="sync")
    def refresh_blog(self, request, object_id):
        back = redirect(reverse("admin:core_sitesettings_change", args=(object_id,)))
        hook = settings.VERCEL_DEPLOY_HOOK_URL
        if not hook:
            messages.error(request, "Blog refresh isn't configured yet (VERCEL_DEPLOY_HOOK_URL is missing). "
                                    "Ask your developer to set it.")
            return back
        try:
            requests.post(hook, timeout=10).raise_for_status()
        except requests.RequestException:
            log.exception("Vercel deploy hook failed")
            messages.error(request, "The website didn't accept the refresh request. Try again in a minute.")
            return back

        SiteSettings.objects.filter(pk=1).update(blog_last_refresh_at=timezone.now())
        messages.success(request, "Refresh started. New Substack posts will appear on the site in about two minutes.")
        return back


# Re-register auth models so staff screens share the Unfold look.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
