from rest_framework import serializers

from .models import PricingTier


class PricingTierSerializer(serializers.ModelSerializer):
    features = serializers.ListField(source="feature_list", child=serializers.CharField())
    highlighted = serializers.BooleanField(source="is_highlighted")

    class Meta:
        model = PricingTier
        fields = ("slug", "name", "audience", "price", "currency", "interval", "description", "features", "highlighted")


class CheckoutSerializer(serializers.Serializer):
    tier = serializers.SlugField()
    email = serializers.EmailField()
    fullName = serializers.CharField(max_length=160, required=False, allow_blank=True)

    def validate_tier(self, slug):
        try:
            return PricingTier.objects.get(slug=slug, is_active=True)
        except PricingTier.DoesNotExist:
            raise serializers.ValidationError("That plan isn't available.")
