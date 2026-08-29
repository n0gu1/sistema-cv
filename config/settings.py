import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("OMITIR_DOTENV", "False").lower() != "true":
    load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-development-key")
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [
    host
    for host in os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com"
    ).split(",")
    if host
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "hello",
    "reclutamiento",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
                "reclutamiento.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "reclutamiento.Usuario"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "index"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "index"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Signed cookies provide persistent sessions without adding another business table.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not DATABASE_URL.startswith("sqlite"),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
PRIVATE_UPLOAD_ROOT = Path(
    os.environ.get("PRIVATE_UPLOAD_ROOT", BASE_DIR / "private_uploads")
)
BACKBLAZE_ENABLED = os.environ.get("BACKBLAZE_ENABLED", "False").lower() == "true"
BACKBLAZE_APPLICATION_KEY_ID = os.environ.get("BACKBLAZE_APPLICATION_KEY_ID", "")
BACKBLAZE_APPLICATION_KEY = os.environ.get("BACKBLAZE_APPLICATION_KEY", "")
BACKBLAZE_BUCKET_NAME = os.environ.get("BACKBLAZE_BUCKET_NAME", "")
BACKBLAZE_ENDPOINT_URL = os.environ.get("BACKBLAZE_ENDPOINT_URL", "")
BACKBLAZE_OBJECT_PREFIX = os.environ.get("BACKBLAZE_OBJECT_PREFIX", "curriculos")
BACKBLAZE_PRESIGNED_URL_EXPIRY = int(
    os.environ.get("BACKBLAZE_PRESIGNED_URL_EXPIRY", "300")
)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_BASE_URL = os.environ.get(
    "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"
)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_TIMEOUT_SECONDS = int(os.environ.get("GROQ_TIMEOUT_SECONDS", "90"))
GROQ_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "2500"))
ANALYSIS_MAX_TEXT_CHARS = int(os.environ.get("ANALYSIS_MAX_TEXT_CHARS", "16000"))
ANALYSIS_OCR_ENABLED = os.environ.get("ANALYSIS_OCR_ENABLED", "True").lower() == "true"
ANALYSIS_OCR_MAX_PAGES = int(os.environ.get("ANALYSIS_OCR_MAX_PAGES", "5"))
ANALYSIS_OCR_DPI = int(os.environ.get("ANALYSIS_OCR_DPI", "150"))
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
TESSERACT_LANG = os.environ.get("TESSERACT_LANG", "spa+eng")

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
CELERY_BROKER_URL = (os.environ.get("CELERY_BROKER_URL") or REDIS_URL).strip()
CELERY_RESULT_BACKEND = (
    os.environ.get("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL
).strip()
ANALYSIS_ASYNC_ENABLED = os.environ.get(
    "ANALYSIS_ASYNC_ENABLED",
    "True" if CELERY_BROKER_URL else "False",
).lower() == "true"
ANALYSIS_TASK_MAX_RETRIES = int(os.environ.get("ANALYSIS_TASK_MAX_RETRIES", "3"))
ANALYSIS_TASK_LEASE_SECONDS = int(
    os.environ.get("ANALYSIS_TASK_LEASE_SECONDS", "900")
)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_DEFAULT_QUEUE = "analysis"
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ROUTES = {
    "reclutamiento.tasks.process_application_analysis": {"queue": "analysis"},
}
CELERY_IMPORTS = ("reclutamiento.tasks",)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"
CELERY_RESULT_EXPIRES = 60 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_TIME_LIMIT = 300
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "reclutamiento.api_pagination.ApiPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Nexo Talento API",
    "DESCRIPTION": "API para plazas, aspirantes, postulaciones y análisis de currículos.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {"name": "Plazas", "description": "Consulta de oportunidades laborales."},
        {"name": "Aspirantes", "description": "Perfiles visibles para RRHH."},
        {"name": "Postulaciones", "description": "Seguimiento y acciones del proceso."},
        {"name": "Catálogos", "description": "Valores de referencia del dominio."},
    ],
}

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "20"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "Sistema CV <no-reply@example.com>",
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
