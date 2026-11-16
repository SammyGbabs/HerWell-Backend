from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .mailchimp import sync_newsletter_lead
from .serializers import LeadSerializer


class LeadCreateView(APIView):
    """POST /api/leads/ → 201 { id }. The contract src/lib/leads.ts already expects."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "leads"

    def post(self, request):
        serializer = LeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Bots fill the hidden field. Answer as if it worked, store nothing.
        if serializer.validated_data.get("website"):
            return Response({"id": None}, status=status.HTTP_201_CREATED)

        lead = serializer.save()
        sync_newsletter_lead(lead)
        return Response({"id": lead.pk}, status=status.HTTP_201_CREATED)
