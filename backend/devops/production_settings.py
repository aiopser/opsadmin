"""Production entry point. All deployment secrets must be supplied explicitly."""

import os

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

SECRET_KEY = os.environ.get("DEVOPS_SECRET_KEY", "")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Production requires a strong DEVOPS_SECRET_KEY")

CREDENTIAL_ENCRYPTION_KEY = os.environ.get("DEVOPS_CREDENTIAL_ENCRYPTION_KEY", "")
try:
    Fernet(CREDENTIAL_ENCRYPTION_KEY.encode())
except (ValueError, TypeError) as exc:
    raise ImproperlyConfigured("Production requires DEVOPS_CREDENTIAL_ENCRYPTION_KEY") from exc

ALLOWED_HOSTS = [value.strip() for value in os.environ.get("DEVOPS_PRODUCTION_ALLOWED_HOSTS", "").split(",") if value.strip()]
CORS_ALLOWED_ORIGINS = [value.strip() for value in os.environ.get("DEVOPS_CORS_ALLOWED_ORIGINS", "").split(",") if value.strip()]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires explicit allowed hosts")
CORS_ORIGIN_WHITELIST = []
CORS_ORIGIN_ALLOW_ALL = False
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
DEBUG = False
DEBUG_DEV = False
DEBUG_ANSIBLE = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
MIDDLEWARE = [*MIDDLEWARE]  # noqa: F405
MIDDLEWARE.insert(MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware"), "django.middleware.csrf.CsrfViewMiddleware")
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY, "ACCESS_TOKEN_LIFETIME": datetime.timedelta(minutes=5)}  # noqa: F405
