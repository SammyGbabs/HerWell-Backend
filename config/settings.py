"""
HerWell backend settings.

Everything environment-specific comes from environment variables, so the same
file runs locally (SQLite, local media) and on Render (Supabase Postgres,
Supabase Storage). See .env.example for the full list.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# Load a local .env when present (development convenience, no extra dependency).
_dotenv = BASE_DIR / ".env"
if _dotenv.exists():
    for line in _dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ── Core ──────────────────────────────────────────────────────────────────────
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Render injects the service hostname; trust it automatically.
if render_host := env("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(render_host)

CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1"}]


# ── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Unfold must come before django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    "storages",
    # HerWell
    "core",
    "content",
    "leads",
    "payments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ── Database ──────────────────────────────────────────────────────────────────
# Local: SQLite. Production: Supabase *Session pooler* URL (port 5432).
# The direct Supabase host is IPv6-only and Render cannot reach it.
DATABASE_URL = env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=60,
        conn_health_checks=True,
        ssl_require=DATABASE_URL.startswith("postgres"),
    )
}
# Only needed if you switch to Supabase's *transaction* pooler (port 6543).
if env_bool("DB_TRANSACTION_POOLER", False):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES["default"]["CONN_MAX_AGE"] = 0


# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── i18n ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True


# ── Static & media ────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Supabase Storage speaks the S3 protocol. When a bucket is configured, uploaded
# PDFs go to a *public* bucket and the API hands out their permanent public URL.
SUPABASE_STORAGE_BUCKET = env("SUPABASE_STORAGE_BUCKET")
if SUPABASE_STORAGE_BUCKET:
    _project_ref = env("SUPABASE_PROJECT_REF")
    _media_backend = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": SUPABASE_STORAGE_BUCKET,
            "endpoint_url": f"https://{_project_ref}.supabase.co/storage/v1/s3",
            "region_name": env("SUPABASE_STORAGE_REGION", "eu-west-1"),
            "access_key": env("SUPABASE_S3_ACCESS_KEY_ID"),
            "secret_key": env("SUPABASE_S3_SECRET_ACCESS_KEY"),
            "custom_domain": f"{_project_ref}.supabase.co/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}",
            "querystring_auth": False,
            "file_overwrite": False,
            "default_acl": None,
            "addressing_style": "path",
        },
    }
else:
    MEDIA_URL = "media/"
    MEDIA_ROOT = BASE_DIR / "media"
    _media_backend = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _media_backend,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Tests run without collectstatic, so there is no manifest to read.
if "test" in sys.argv[1:2]:
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}

DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── API ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_RATES": {
        "leads": "10/hour",
        "checkout": "20/hour",
    },
    "UNAUTHENTICATED_USER": None,
}

# The React site lives on another origin (Vercel); it may call /api/ only.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_URLS_REGEX = r"^/api/.*$"


# ── Integrations ──────────────────────────────────────────────────────────────
# Secrets live here, in environment variables. Never in the admin.
PAYSTACK_SECRET_KEY = env("PAYSTACK_SECRET_KEY")
PAYSTACK_CALLBACK_URL = env("PAYSTACK_CALLBACK_URL")    # where Paystack returns the buyer
MAILCHIMP_API_KEY = env("MAILCHIMP_API_KEY")            # "<key>-us21" style; DC is the suffix
VERCEL_DEPLOY_HOOK_URL = env("VERCEL_DEPLOY_HOOK_URL")  # rebuilds the site to pull new Substack posts


# ── Security (production) ─────────────────────────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

SESSION_COOKIE_AGE = 60 * 60 * 8  # staff sessions expire after a working day

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}


# ── Admin look & navigation (Unfold) ──────────────────────────────────────────
UNFOLD = {
    "SITE_TITLE": "HerWell Admin",
    "SITE_HEADER": "HerWell",
    "SITE_SUBHEADER": "Website dashboard",
    "SITE_SYMBOL": "spa",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "STYLES": [lambda request: static("admin/herwell.css")],
    # HerWell plum (#59295E) as the primary scale.
    "COLORS": {
        "primary": {
            "50": "oklch(97.1% .014 330)",
            "100": "oklch(94.4% .03 330)",
            "200": "oklch(89% .06 330)",
            "300": "oklch(81% .1 330)",
            "400": "oklch(70% .14 328)",
            "500": "oklch(58% .15 326)",
            "600": "oklch(48% .14 324)",
            "700": "oklch(40% .12 322)",
            "800": "oklch(34% .1 320)",
            "900": "oklch(29% .08 320)",
            "950": "oklch(20% .06 320)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Website content",
                "items": [
                    {"title": "Resources & downloads", "icon": "download", "link": reverse_lazy("admin:content_resource_changelist")},
                    {"title": "Videos", "icon": "smart_display", "link": reverse_lazy("admin:content_video_changelist")},
                    {"title": "Events & webinars", "icon": "event", "link": reverse_lazy("admin:content_event_changelist")},
                ],
            },
            {
                "title": "Inbox",
                "items": [
                    {"title": "Form submissions", "icon": "inbox", "link": reverse_lazy("admin:leads_lead_changelist")},
                ],
            },
            {
                "title": "Payments",
                "items": [
                    {"title": "Pricing tiers", "icon": "sell", "link": reverse_lazy("admin:payments_pricingtier_changelist")},
                    {"title": "Transactions & gateway", "icon": "receipt_long", "link": reverse_lazy("admin:payments_transaction_changelist")},
                ],
            },
            {
                "title": "Settings",
                "items": [
                    {"title": "Site settings & blog", "icon": "settings", "link": reverse_lazy("admin:core_sitesettings_changelist")},
                    {"title": "Staff users", "icon": "person", "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Staff groups", "icon": "group", "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}
