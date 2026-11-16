from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from content.views import EventListView, ResourceListView, VideoListView
from core.views import SiteSettingsView, healthz
from leads.views import LeadCreateView
from payments.views import CheckoutStatusView, CheckoutView, PaystackWebhookView, PricingListView

admin.site.site_title = "HerWell Admin"
admin.site.site_header = "HerWell"

api = [
    path("settings/", SiteSettingsView.as_view()),
    path("resources/", ResourceListView.as_view()),
    path("videos/", VideoListView.as_view()),
    path("events/", EventListView.as_view()),
    path("leads/", LeadCreateView.as_view()),
    path("pricing/", PricingListView.as_view()),
    path("checkout/", CheckoutView.as_view()),
    path("checkout/status/", CheckoutStatusView.as_view()),
    path("payments/paystack/webhook/", PaystackWebhookView.as_view()),
]

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("healthz", healthz),
    path("admin/", admin.site.urls),
    path("api/", include(api)),
]

if settings.DEBUG and hasattr(settings, "MEDIA_ROOT"):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
