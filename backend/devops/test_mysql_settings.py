"""Opt-in local disposable MySQL tests; never read deployment DB settings."""

import os
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured

from .test_full_settings import *  # noqa: F403

if os.environ.get("DEVOPS_TEST_MYSQL_ISOLATED") != "yes":
    raise ImproperlyConfigured("Explicit isolated MySQL test opt-in is required")

port = os.environ.get("DEVOPS_TEST_MYSQL_PORT", "")
if not port.isdigit() or not 1024 <= int(port) <= 65535 or port == "3306":
    raise ImproperlyConfigured("Use a dedicated local container MySQL port, not 3306")

database_name = f"test_devops_{uuid4().hex}"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": "127.0.0.1",
        "PORT": port,
        "NAME": database_name,
        "USER": os.environ["DEVOPS_TEST_MYSQL_USER"],
        "PASSWORD": os.environ["DEVOPS_TEST_MYSQL_PASSWORD"],
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"NAME": database_name},
    }
}
