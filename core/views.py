from django.db import connection
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SiteSettings
from .serializers import SiteSettingsSerializer


def healthz(request):
    """
    Uptime-monitor target. Pinging this every ~10 minutes keeps the Render free
    instance awake, and the query keeps the Supabase free project from pausing.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"ok": False}, status=503)
    return JsonResponse({"ok": True})


class SiteSettingsView(APIView):
    def get(self, request):
        data = SiteSettingsSerializer(SiteSettings.load()).data
        return Response(data, headers={"Cache-Control": "public, max-age=300"})
