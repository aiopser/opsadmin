"""Read-only runtime diagnostics without credentials or local installation paths."""

import importlib.metadata
import importlib.util
import os

from cryptography.fernet import Fernet
from django.conf import settings


def release_id():
    release = (
        os.environ.get("DEVOPS_RELEASE", "").strip()
        or os.environ.get("COMMIT_SHA", "").strip()
    )
    return release[:100] or "unknown"


def runtime_environment(worker_versions=None, worker_names=()):
    sdks = []
    for name, module in (
        ("alibabacloud-ecs20140526", "alibabacloud_ecs20140526"),
        ("tencentcloud-sdk-python-cvm", "tencentcloud.cvm"),
    ):
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError, OSError):
            available = False
        try:
            version = importlib.metadata.version(name) if available else None
        except (importlib.metadata.PackageNotFoundError, ValueError, OSError):
            version = None
        sdks.append({"name": name, "available": available, "version": version})
    key = getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", "")
    try:
        Fernet(key.encode() if isinstance(key, str) else key)
        valid = True
    except (ValueError, TypeError):
        valid = False
    version = release_id()
    reported = (
        {
            name: str(info["version"])[:100]
            for name, info in (worker_versions or {}).items()
            if isinstance(info, dict)
            and isinstance(info.get("version"), str)
            and info["version"] != "unknown"
        }
        if isinstance(worker_versions, dict)
        else {}
    )
    status = "not_reported"
    if version != "unknown" and any(item != version for item in reported.values()):
        status = "mismatch"
    elif version != "unknown" and worker_names and set(worker_names).issubset(reported):
        status = "matched"
    return {
        "sdks": sdks,
        "credentialsEncryptionConfigured": bool(key),
        "credentialsEncryptionValid": valid,
        "apiVersion": version,
        "workersVersionStatus": status,
        "workerVersions": reported,
    }
