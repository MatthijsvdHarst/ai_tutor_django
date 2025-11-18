"""
Django settings for ai_tutor_django project, configured via environment variables.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse

# Paths ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]

load_dotenv(BASE_DIR / '.env')
DEBUG = env_bool('DJANGO_DEBUG', True)


def parse_database_url(url: str) -> dict:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in {"sqlite", "sqlite3"}:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path if parsed.path else (BASE_DIR / "db.sqlite3"),
        }
    if scheme in {"postgres", "postgresql", "psql"}:
        engine = "django.db.backends.postgresql"
    elif scheme in {"mysql", "mariadb"}:
        engine = "django.db.backends.mysql"
    else:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme}")
    return {
        "ENGINE": engine,
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or "",
    }


# Security ------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me-in-production")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Applications --------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "alers.apps.AlersConfig",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ai_tutor_django.urls"

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

WSGI_APPLICATION = "ai_tutor_django.wsgi.application"


# Database ------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}



# Authentication ------------------------------------------------------------
AUTH_USER_MODEL = "alers.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"


# Internationalization ------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# STATIC
# ----------------------------------------------------------------------

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STATIC_URL = "/static/"

STATICFILES_DIRS = [BASE_DIR / "ai_tutor_django/static"]

# MEDIA
# ----------------------------------------------------------------------

MEDIA_URL = "/media/"

MEDIA_ROOT = os.getenv("MEDIA_ROOT", default=BASE_DIR / ".media")


# Misc ----------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_COMPLETION_TIMEOUT = int(os.getenv("OPENAI_COMPLETION_TIMEOUT", "60"))

# if OPENAI_API_KEY:
#     os.environ.setdefault("OPENAI_API_KEY", OPENAI_API_KEY)
