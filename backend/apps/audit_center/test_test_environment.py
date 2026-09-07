"""Safety requirements for both SQLite test configurations."""

from pathlib import Path

from django.conf import settings


def test_background_dispatch_cannot_reach_deployment_broker():
    broker_is_isolated = settings.CELERY_BROKER_URL == "memory://"
    backend_is_isolated = settings.CELERY_RESULT_BACKEND == "cache+memory://"
    assert broker_is_isolated, "Test broker must use memory transport"
    assert backend_is_isolated, "Test results must use memory storage"
    assert settings.CELERY_BEAT_SCHEDULE == {}
    assert settings.CELERY_TASK_DEFAULT_QUEUE.startswith("devops-test-")
    assert settings.CELERY_TASK_ROUTES == {}


def test_runtime_files_are_isolated_from_deployment():
    root = Path(settings.TEST_RUNTIME_ROOT)
    for directory in (settings.MEDIA_ROOT, settings.CELERY_LOG_DIR, settings.SHARE_DIR):
        assert Path(directory).is_relative_to(root)
    assert root != Path(settings.BASE_DIR) / "data"
