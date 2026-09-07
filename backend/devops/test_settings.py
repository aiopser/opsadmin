"""Settings used by the automated test suite.

Tests must be reproducible without access to the deployment MySQL or Redis
instances configured in ``config/devops.ini``.  Runtime commands continue to
use :mod:`devops.settings`; pytest selects this module explicitly.
"""

import tempfile
from pathlib import Path
from uuid import uuid4
from cryptography.fernet import Fernet

from .settings import *  # noqa: F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "devops-platform-tests",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_DEFAULT_QUEUE = f"devops-test-{uuid4().hex}"
CELERY_TASK_ROUTES = {}
CELERY_BEAT_SCHEDULE = {}
TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="devops-test-"))
MEDIA_ROOT = str(TEST_RUNTIME_ROOT / "media")
CELERY_LOG_DIR = str(TEST_RUNTIME_ROOT / "celery")
SHARE_DIR = str(TEST_RUNTIME_ROOT / "share")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SECRET_KEY = "devops-isolated-tests-only-never-use-in-deployment"
CREDENTIAL_ENCRYPTION_KEY = Fernet.generate_key().decode()
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
