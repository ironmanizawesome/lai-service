"""Django settings for laihub project.

Settings are read from environment variables via django-environ. See `.env.example`
for the list of variables; copy to `.env` for local development.
"""

import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
# ENV_FILE lets the home GPU worker load a separate env file (cloud DB/Redis/R2)
# without clobbering the local dev .env. Defaults to the repo-root .env.
environ.Env.read_env(os.environ.get("ENV_FILE", str(BASE_DIR / ".env")))

# ---- Core --------------------------------------------------------------------

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="dev-insecure-change-me-for-production",
)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# CSRF trusted origins — needed when serving over an https tunnel (ngrok) for
# mobile QA, since the Origin/Referer host differs from localhost. Supply the
# full scheme+host, e.g. CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Render injects the service's public hostname as RENDER_EXTERNAL_HOSTNAME.
# Trust it automatically so the *.onrender.com domain needs no manual config.
_render_host = env("RENDER_EXTERNAL_HOSTNAME", default="")
if _render_host:
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [_render_host]
    CSRF_TRUSTED_ORIGINS = list(CSRF_TRUSTED_ORIGINS) + [f"https://{_render_host}"]

SITE_ID = 1
ROOT_URLCONF = "laihub.urls"
WSGI_APPLICATION = "laihub.wsgi.application"
ASGI_APPLICATION = "laihub.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ---- Apps --------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_extensions",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.projects",
    "apps.measurements",
    "apps.pipeline",
    "apps.results",
    "apps.analytics",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---- Middleware --------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# ---- Templates ---------------------------------------------------------------

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

# ---- Database (SQLite for M1; switch via DATABASE_URL at M6) ------------------

if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db_url("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---- Auth backends + allauth -------------------------------------------------

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_SESSION_REMEMBER = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
    },
}

# ---- Password validation -----------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---- i18n / time -------------------------------------------------------------

LANGUAGE_CODE = "ko"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ---- Static + media ----------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Object storage (S3-compatible / Cloudflare R2) for the M6 split deployment.
# When AWS_STORAGE_BUCKET_NAME is set, the default file storage switches to
# object storage so the cloud web tier (uploads) and the home GPU worker
# (results) can share files without a shared local filesystem. Unset in dev →
# local FileSystemStorage under MEDIA_ROOT (no boto3 import, no behaviour change).
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")

if AWS_STORAGE_BUCKET_NAME:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")  # R2: https://<acct>.r2.cloudflarestorage.com
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="auto")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None              # R2 ignores ACLs; keep objects private
    AWS_QUERYSTRING_AUTH = True         # serve user media via short-lived signed URLs
    AWS_QUERYSTRING_EXPIRE = env.int("AWS_QUERYSTRING_EXPIRE", default=3600)

    # Optional public custom domain (R2 public bucket). If set, URLs are public
    # (no signing) — only enable if the bucket is meant to be world-readable.
    _r2_custom_domain = env("AWS_S3_CUSTOM_DOMAIN", default="")
    if _r2_custom_domain:
        AWS_S3_CUSTOM_DOMAIN = _r2_custom_domain
        AWS_QUERYSTRING_AUTH = False

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# ---- Email -------------------------------------------------------------------

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@laihub.local")

# ---- Celery ------------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")

# Upstash Redis uses TLS (rediss://) with a managed cert — disable cert verification
if CELERY_BROKER_URL.startswith("rediss://"):
    import ssl as _ssl
    _redis_ssl = {"ssl_cert_reqs": _ssl.CERT_NONE}
    CELERY_BROKER_USE_SSL = _redis_ssl
    CELERY_REDIS_BACKEND_USE_SSL = _redis_ssl

CELERY_TASK_ROUTES = {
    "apps.pipeline.tasks.reconstruct": {"queue": "gpu"},
    "apps.pipeline.tasks.*": {"queue": "cpu"},
}
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab as _crontab
CELERY_BEAT_SCHEDULE = {
    "clean-stale-npz-daily": {
        "task": "apps.pipeline.tasks.clean_stale_npz",
        "schedule": _crontab(hour=3, minute=0),  # 매일 새벽 3시 (워커 타임존 기준)
    },
}

# ---- File upload limits ------------------------------------------------------

DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100 MB inline (videos stream to disk)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB before spooling to /tmp

# ---- LingBot-Map pipeline (M3+) ----------------------------------------------
# LINGBOT_MAP_ROOT: absolute path to the lingbot-map repo (precompute_npz.py lives here).
# LINGBOT_MAP_PYTHON: Python interpreter that has torch + lingbot_map installed (conda env).
# LINGBOT_MAP_MODEL_PATH: absolute or relative-to-root path to the checkpoint .pt file.

LINGBOT_MAP_ROOT = env("LINGBOT_MAP_ROOT", default="")
LINGBOT_MAP_PYTHON = env("LINGBOT_MAP_PYTHON", default="python")
LINGBOT_MAP_MODEL_PATH = env(
    "LINGBOT_MAP_MODEL_PATH",
    default="checkpoints/lingbot-map-long.pt",
)

# ---- Logging -----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# ---- Security (relaxed in DEBUG, tightened in prod) --------------------------

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
