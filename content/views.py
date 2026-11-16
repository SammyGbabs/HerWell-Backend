from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Audience, Event, Resource, Video
from .serializers import EventSerializer, ResourceSerializer, VideoSerializer

CACHE = {"Cache-Control": "public, max-age=60"}


class ResourceListView(ListAPIView):
    """GET /api/resources/?audience=employer|individual"""

    serializer_class = ResourceSerializer

    def get_queryset(self):
        qs = Resource.objects.filter(is_published=True)
        audience = self.request.query_params.get("audience")
        if audience in Audience.values:
            qs = qs.filter(audience=audience)
        return qs

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        for header, value in CACHE.items():
            response[header] = value
        return response


class VideoListView(APIView):
    """GET /api/videos/ → { home: {...}, employer: {...}, individual: {...} }"""

    def get(self, request):
        videos = Video.objects.filter(is_published=True)
        data = {v.placement: VideoSerializer(v).data for v in videos if v.youtube_id}
        return Response(data, headers=CACHE)


class EventListView(APIView):
    """GET /api/events/ → { upcoming: [...], past: [...] }. Sorted by date, nothing to file manually."""

    PAST_LIMIT = 12

    def get(self, request):
        published = Event.objects.filter(is_published=True)
        return Response(
            {
                "upcoming": EventSerializer(published.upcoming(), many=True).data,
                "past": EventSerializer(published.past()[: self.PAST_LIMIT], many=True).data,
            },
            headers=CACHE,
        )
