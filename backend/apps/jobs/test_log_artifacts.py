import pytest
from django.conf import settings as django_settings
from django.core.exceptions import SuspiciousFileOperation

from apps.jobs.log_artifacts import archive_stdout, iter_run_stdout
from apps.jobs.models import RunLogChunk, WorkerPool, WorkflowRun


@pytest.fixture
def log_run(user, settings, tmp_path):
    settings.STORAGES = {
        **django_settings.STORAGES,
        "job_logs": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path)},
        },
    }
    settings.JOBS_LOG_MAX_BYTES = 1024 * 1024
    pool = WorkerPool.objects.create(code="logs", name="Logs", queue_name="test")
    return WorkflowRun.objects.create(worker_pool=pool, triggered_by=user)


@pytest.mark.django_db
def test_utf8_ansi_and_download_chunks_are_preserved(log_run):
    text = "\x1b[31m中文 output\x1b[0m\n" * 10000
    archive_stdout(run_id=log_run.id, sequence=1, text=text)
    chunks = list(iter_run_stdout(log_run.id, block_size=31))
    assert all(len(chunk) <= 31 for chunk in chunks)
    assert b"".join(chunks).decode("utf-8") == text


@pytest.mark.django_db
def test_log_size_limit_preserves_valid_utf8(log_run, settings):
    settings.JOBS_LOG_MAX_BYTES = 8
    archive_stdout(run_id=log_run.id, sequence=1, text="中文中文中文")
    archive_stdout(run_id=log_run.id, sequence=2, text="more")
    raw = b"".join(iter_run_stdout(log_run.id))
    assert len(raw) <= 8
    raw.decode("utf-8")
    assert RunLogChunk.objects.filter(workflow_run=log_run, truncated=True).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "job-logs/run-999/1-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.log",
        "C:\\secret",
    ],
)
def test_untrusted_storage_paths_are_rejected(log_run, name):
    RunLogChunk.objects.create(
        workflow_run=log_run, sequence=1, storage_name=name, byte_count=1
    )
    with pytest.raises(SuspiciousFileOperation):
        list(iter_run_stdout(log_run.id))


@pytest.mark.django_db
def test_repeated_archive_does_not_duplicate_bytes(log_run):
    archive_stdout(run_id=log_run.id, sequence=1, text="one")
    archive_stdout(run_id=log_run.id, sequence=1, text="one")
    assert b"".join(iter_run_stdout(log_run.id)) == b"one"
    assert RunLogChunk.objects.filter(workflow_run=log_run).count() == 1


@pytest.mark.django_db(transaction=True)
def test_no_log_is_not_archived_and_failure_preserves_safe_output(log_run):
    from apps.jobs.events import append_run_event
    from apps.jobs.models import NodeRun

    node = NodeRun.objects.create(workflow_run=log_run)
    append_run_event(
        run_id=log_run.id,
        node_run_id=node.id,
        event_key="hidden",
        event={
            "event": "runner_on_ok",
            "event_data": {"res": {"_ansible_no_log": True, "stdout": "hidden-value"}},
        },
    )
    append_run_event(
        run_id=log_run.id,
        node_run_id=node.id,
        event_key="failed",
        event={
            "event": "runner_on_failed",
            "event_data": {
                "res": {"stdout": "password=hidden-value", "stderr": "failed safely"}
            },
        },
    )
    log_run.status = "failed"
    log_run.save()
    output = b"".join(iter_run_stdout(log_run.id)).decode()
    assert "hidden-value" not in output
    assert "failed safely" in output
    assert "[REDACTED]" in output


@pytest.mark.django_db
def test_log_download_requires_owner_and_rejects_path_parameters(log_run, user):
    from rest_framework.test import APIClient
    from apps.permission.models import Permission, Role
    from apps.permission.services import sync_casbin_rules, CasbinEnforcerService

    role = Role.objects.create(name="Log reader")
    role.permission.add(
        Permission.objects.create(
            name="Read log",
            code="test.log.read",
            type="api",
            path="/api/v1/tasks/runs/:id/log",
            method="GET",
        )
    )
    user.role.add(role)
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    client = APIClient()
    client.force_authenticate(user)
    archive_stdout(run_id=log_run.id, sequence=1, text="safe output")
    response = client.get(f"/api/v1/tasks/runs/{log_run.id}/log")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"safe output"
    assert "storage_name" not in str(response.headers)
    assert (
        client.get(f"/api/v1/tasks/runs/{log_run.id}/log?path=../../secret").status_code
        == 400
    )
    log_run.triggered_by = None
    log_run.save()
    assert client.get(f"/api/v1/tasks/runs/{log_run.id}/log").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_archive_failure_does_not_rollback_event(log_run):
    from unittest.mock import patch
    from apps.jobs.events import append_run_event
    from apps.jobs.models import JobEventLog

    with patch(
        "apps.jobs.log_artifacts.archive_stdout",
        side_effect=OSError("isolated storage failure"),
    ):
        append_run_event(
            run_id=log_run.id,
            event_key="stored-event",
            event={
                "event": "runner_on_ok",
                "event_data": {"res": {"stdout": "available in event"}},
            },
        )
    assert JobEventLog.objects.filter(workflow_run=log_run).count() == 1
