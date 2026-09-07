import os
import uuid

from django.conf import settings


def get_task_log_path(task_id):
    try:
        task_id = str(uuid.UUID(str(task_id)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Invalid task id")
    base_path = getattr(
        settings, "CELERY_LOG_DIR", os.path.join(settings.BASE_DIR, "data", "celery")
    )
    path = os.path.join(base_path, task_id[0], task_id[1], f"{task_id}.log")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path
