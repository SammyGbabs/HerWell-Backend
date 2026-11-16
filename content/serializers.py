from django.conf import settings
from rest_framework import serializers

from .models import Event, Resource, Video


class ResourceSerializer(serializers.ModelSerializer):
    fileUrl = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = ("id", "title", "badge", "description", "audience", "icon", "fileUrl")

    def get_fileUrl(self, obj: Resource) -> str | None:
        if not obj.file:
            return None
        url = obj.file.url
        request = self.context.get("request")
        # Local filesystem storage returns a relative URL; make it absolute.
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        # The file lives on another origin (Supabase), where browsers ignore the
        # `download` attribute and would navigate away to the PDF. This flag makes
        # Supabase send it as an attachment, so it downloads in place.
        if settings.SUPABASE_STORAGE_BUCKET:
            return f"{url}?download"
        return url


class VideoSerializer(serializers.ModelSerializer):
    youtubeId = serializers.CharField(source="youtube_id", read_only=True)

    class Meta:
        model = Video
        fields = ("placement", "youtubeId", "title", "duration", "eyebrow", "heading", "blurb")


class EventSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="get_event_type_display")
    startsAt = serializers.DateTimeField(source="starts_at")
    registrationUrl = serializers.URLField(source="registration_url")
    recordingUrl = serializers.URLField(source="recording_url")

    class Meta:
        model = Event
        fields = ("id", "title", "type", "startsAt", "speaker", "registrationUrl", "recordingUrl")
