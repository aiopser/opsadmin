import pytest
from django.conf import settings as django_settings
from django.core.exceptions import SuspiciousFileOperation

from apps.jobs.log_artifacts import archive_stdout, iter_run_stdout
from apps.jobs.models import RunLogChunk, WorkerPool, WorkflowRun


@pytest.mark.django_db
def test_purge_removes_only_expired_archived_files(log_run, settings):
    from datetime import timedelta
    from django.utils import timezone
    from apps.jobs.log_artifacts import job_log_storage, purge_expired_archives

    settings.JOBS_LOG_RETENTION_DAYS = 30
    now = timezone.now()
    for sequence in (1, 2, 3):
        archive_stdout(run_id=log_run.id, sequence=sequence, text="retained output")
    expired, boundary, failed = list(
        RunLogChunk.objects.filter(workflow_run=log_run).order_by("sequence")
    )
    RunLogChunk.objects.filter(pk=expired.pk).update(created_at=now - timedelta(days=31))
    RunLogChunk.objects.filter(pk=boundary.pk).update(created_at=now - timedelta(days=30))
    RunLogChunk.objects.filter(pk=failed.pk).update(
        created_at=now - timedelta(days=31), status=RunLogChunk.Status.FAILED
    )

    assert purge_expired_archives(now=now) == 1
    assert not RunLogChunk.objects.filter(pk=expired.pk).exists()
    assert not job_log_storage().exists(expired.storage_name)
    for chunk in (boundary, failed):
        assert RunLogChunk.objects.filter(pk=chunk.pk).exists()
        assert job_log_storage().exists(chunk.storage_name)


def test_recovery_continues_after_archive_purge_failure(monkeypatch, caplog):
    from apps.jobs.tasks import recover_stale_workflow_runs

    monkeypatch.setattr("apps.jobs.tasks.deliver_pending_dispatches", lambda: 1)
    monkeypatch.setattr("apps.jobs.tasks.recover_stale_executions", lambda: 2)
    monkeypatch.setattr("apps.jobs.log_artifacts.rearchive_failed_chunks", lambda: 3)
    monkeypatch.setattr("apps.jobs.log_artifacts.recover_pending_archives", lambda: 4)
    monkeypatch.setattr("apps.jobs.alerts.recover_alerts", lambda: 5)

    def unavailable():
        raise OSError("archive storage unavailable")

    monkeypatch.setattr("apps.jobs.log_artifacts.purge_expired_archives", unavailable)
    result = recover_stale_workflow_runs()
    assert result["archiveRequests"] == 4
    assert result["notificationAlerts"] == 5
    assert result["errors"] == ["purgedArchives"]
    assert "purgedArchives" in caplog.text


@pytest.mark.django_db
def test_purge_retries_failed_file_deletion(log_run, monkeypatch):
    from datetime import timedelta
    from unittest.mock import patch
    from django.utils import timezone
    from apps.jobs.log_artifacts import job_log_storage, purge_expired_archives

    archive_stdout(run_id=log_run.id, sequence=1, text="expired output")
    chunk = RunLogChunk.objects.get(workflow_run=log_run)
    RunLogChunk.objects.filter(pk=chunk.pk).update(
        created_at=timezone.now() - timedelta(days=31)
    )
    storage = job_log_storage()
    monkeypatch.setattr("apps.jobs.log_artifacts.job_log_storage", lambda: storage)
    with patch.object(storage, "delete", side_effect=OSError("storage unavailable")):
        assert purge_expired_archives() == 0
    assert RunLogChunk.objects.filter(pk=chunk.pk).exists()
    assert storage.exists(chunk.storage_name)
    assert purge_expired_archives() == 1
    assert not RunLogChunk.objects.filter(pk=chunk.pk).exists()
    assert not storage.exists(chunk.storage_name)


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


@pytest.mark.django_db
def test_queue_event_stdout_archive_stages_encrypted_request_once(log_run):
    from apps.cmdb.crypto import decrypt_secret
    from apps.jobs.log_artifacts import queue_event_stdout_archive
    from apps.jobs.models import RunLogArchiveRequest

    event = {"result": {"stdout": "first output"}, "no_log": False}
    queue_event_stdout_archive(log_run.id, 1, event)
    queue_event_stdout_archive(log_run.id, 1, event)

    assert RunLogArchiveRequest.objects.filter(workflow_run=log_run).count() == 1
    request = RunLogArchiveRequest.objects.get(workflow_run=log_run, sequence=1)
    assert request.status == RunLogArchiveRequest.Status.PENDING
    assert request.reserved_bytes == len("first output\n")
    assert "first output" not in request.content_encrypted
    assert decrypt_secret(request.content_encrypted) == "first output\n"


@pytest.mark.django_db
def test_process_archive_request_writes_chunk_and_completes(log_run):
    from apps.cmdb.crypto import encrypt_secret
    from apps.jobs.log_artifacts import process_archive_request
    from apps.jobs.models import RunLogArchiveRequest

    request = RunLogArchiveRequest.objects.create(
        workflow_run=log_run,
        sequence=1,
        content_encrypted=encrypt_secret("queued output\n"),
        reserved_bytes=len("queued output\n"),
    )

    assert process_archive_request(request.id) is True
    request.refresh_from_db()
    assert request.status == RunLogArchiveRequest.Status.STORED
    assert request.content_encrypted == ""
    assert b"".join(iter_run_stdout(log_run.id)) == b"queued output\n"
    assert process_archive_request(request.id) is False


@pytest.mark.django_db
def test_recover_pending_archives_resets_stale_claims(log_run):
    from datetime import timedelta
    from django.utils import timezone
    from apps.cmdb.crypto import encrypt_secret
    from apps.jobs.log_artifacts import recover_pending_archives
    from apps.jobs.models import RunLogArchiveRequest

    stale = RunLogArchiveRequest.objects.create(
        workflow_run=log_run,
        sequence=1,
        content_encrypted=encrypt_secret("recovered output\n"),
        reserved_bytes=len("recovered output\n"),
        status=RunLogArchiveRequest.Status.PROCESSING,
    )
    RunLogArchiveRequest.objects.filter(pk=stale.pk).update(
        updated_at=timezone.now() - timedelta(minutes=10)
    )

    archived = recover_pending_archives()

    assert archived == 1
    stale.refresh_from_db()
    assert stale.status == RunLogArchiveRequest.Status.STORED
    assert stale.retry_count == 1
    assert b"".join(iter_run_stdout(log_run.id)) == b"recovered output\n"
