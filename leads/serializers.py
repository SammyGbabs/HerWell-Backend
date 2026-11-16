from rest_framework import serializers

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    """Accepts the LeadPayload shape the React app already sends (camelCase)."""

    fullName = serializers.CharField(source="full_name", max_length=160, required=False, allow_blank=True)
    # Honeypot: real visitors never see or fill this field.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Lead
        fields = (
            "id", "intent", "audience", "fullName", "email", "organisation", "role",
            "message", "resource", "consent", "source", "website",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "organisation": {"required": False, "allow_blank": True},
            "role": {"required": False, "allow_blank": True},
            "message": {"required": False, "allow_blank": True, "max_length": 5000},
            "resource": {"required": False, "allow_blank": True},
            "source": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        # Only the quick email-only forms (newsletter, community downloads) may omit a name.
        if attrs.get("intent") in (Lead.Intent.BOOK_DEMO, Lead.Intent.GENERAL_ENQUIRY):
            if not attrs.get("full_name", "").strip():
                raise serializers.ValidationError({"fullName": "Please tell us your name."})
        if attrs.get("audience") == Lead.Audience.EMPLOYER and attrs.get("intent") == Lead.Intent.BOOK_DEMO:
            if not attrs.get("organisation", "").strip():
                raise serializers.ValidationError({"organisation": "Please tell us your organisation."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)
