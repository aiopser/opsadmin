"""Settings used by the automated test suite.

Tests must be reproducible without access to the deployment MySQL or Redis
instances configured in ``config/devops.ini``.  Runtime commands continue to
use :mod:`devops.settings`; pytest selects this module explicitly.
"""

import os
import tempfile
from pathlib import Path
from uuid import uuid4
from cryptography.fernet import Fernet

# Load the shared settings without ever opening a deployment INI. Required
# bootstrap values are fictitious; database/broker/storage are replaced below.
os.environ.update(
    {
        "DEVOPS_CONFIG_FILE": "",
        "DEVOPS_DEBUG": "false",
        "DEVOPS_ALLOWED_HOSTS": "['localhost', 'testserver']",
        "DEVOPS_STATIC_URL": "/static/",
        "DEVOPS_JWT_EXPIRATION_DELTA": "3600",
        "DEVOPS_MEDIA_ROOT": str(Path(tempfile.gettempdir()) / "devops-test-bootstrap"),
        "DEVOPS_MYSQL_HOST": "127.0.0.1",
        "DEVOPS_MYSQL_PORT": "3306",
        "DEVOPS_MYSQL_NAME": "unused_test",
        "DEVOPS_MYSQL_USER": "unused_test",
        "DEVOPS_MYSQL_PASSWORD": "unused_test",
        "DEVOPS_MYSQL_OPTIONS": "{}",
        "DEVOPS_REDIS_HOST": "127.0.0.1",
        "DEVOPS_REDIS_PORT": "6379",
        "DEVOPS_REDIS_PASSWORD": "",
        "DEVOPS_PROVISIONING_ENABLED": "0",
        "DEVOPS_PROVISIONING_STATE_KEYS": "{}",
        "DEVOPS_PROVISIONING_STATE_ACTIVE_KEY_ID": "",
        "DEVOPS_PROVISIONING_MONITOR_TEMPLATE_ID": "0",
        "DEVOPS_PROVISIONING_TEMPLATE_ROOT": "",
        "DEVOPS_TERRAFORM_BINARY": "",
        "DEVOPS_TERRAFORM_VERSION": "",
        "DEVOPS_TERRAFORM_CLI_CONFIG": "",
    }
)

from .settings import *  # noqa: F403,E402


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
SHARE_DIR = str(TEST_RUNTIME_ROOT / "share")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
SECRET_KEY = "devops-isolated-tests-only-never-use-in-deployment"
CREDENTIAL_ENCRYPTION_KEY = Fernet.generate_key().decode()
PROVISIONING_STATE_KEYS = {"test-v1": Fernet.generate_key().decode()}
PROVISIONING_STATE_ACTIVE_KEY_ID = "test-v1"
PROVISIONING_ARTIFACT_ROOT = str(TEST_RUNTIME_ROOT / "provisioning")
PROVISIONING_BACKUP_ROOT = str(TEST_RUNTIME_ROOT / "provisioning-backup")
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

JOBS_REALTIME_REDIS_URL = ""
JOBS_REALTIME_ALLOWED_ORIGINS = ["http://localhost:9527"]

JOBS_LOG_ROOT = str(TEST_RUNTIME_ROOT / "job-logs")
STORAGES = {
    **STORAGES,
    "job_logs": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": JOBS_LOG_ROOT},
    },
}  # noqa: F405
