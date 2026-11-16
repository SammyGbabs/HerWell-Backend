from rest_framework import serializers

from .models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    """camelCase keys to match the React codebase."""

    contactEmail = serializers.EmailField(source="contact_email")
    whatsappCommunityUrl = serializers.URLField(source="whatsapp_community_url")
    substackUrl = serializers.URLField(source="substack_url")
    social = serializers.SerializerMethodField()

    class Meta:
        model = SiteSettings
        fields = ("contactEmail", "whatsappCommunityUrl", "substackUrl", "social")

    def get_social(self, obj: SiteSettings) -> dict[str, str]:
        links = {
            "linkedin": obj.linkedin_url,
            "instagram": obj.instagram_url,
            "facebook": obj.facebook_url,
            "x": obj.x_url,
            "youtube": obj.youtube_url,
            "tiktok": obj.tiktok_url,
        }
        return {name: url for name, url in links.items() if url}
