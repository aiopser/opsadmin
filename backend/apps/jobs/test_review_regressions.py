"""Regression coverage for the 2026-10-19 cross-module review."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.jobs.test_schedule_one_off import (
    actor,
    host,
    pool,
    version,
    make_schedule,
    clocked_occurrence,
)
from apps.jobs.models import ScheduledJob, ScheduledJobOutcome, WorkflowRun
from apps.jobs.scheduler import ScheduledJobEntry
from apps.jobs.schedule_sync import periodic_task_name
from apps.jobs.tasks import execute_scheduled_job, deliver_scheduled_catchups


@pytest.mark.django_db
def test_review_beat_retirement_must_not_drop_published_once(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        schedule_type="once",
        run_at=timezone.now() - timedelta(seconds=10),
    )
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    payload = json.loads(task.kwargs)
    entry = next(ScheduledJobEntry(task))
    entry.save()
    entry.is_due()
    task.refresh_from_db()
    assert task.enabled is False
    result = execute_scheduled_job(
        **payload, scheduled_for=clocked_occurrence(schedule)
    )
    assert result["status"] == "dispatched", result


@pytest.mark.django_db
def test_review_catchup_must_respect_expiry(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        pending_dispatch=True,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    ScheduledJobOutcome.objects.create(
        scheduled_job=schedule,
        scheduled_for=timezone.now() - timedelta(minutes=2),
        outcome="overlap_queued",
    )
    deliver_scheduled_catchups()
    assert WorkflowRun.objects.count() == 0
    schedule.refresh_from_db()
    assert schedule.enabled is False
    assert schedule.pending_dispatch is False
    assert ScheduledJobOutcome.objects.get(scheduled_job=schedule).outcome == "expired"


@pytest.mark.django_db
def test_review_cloud_resync_preserves_manual_connection():
    from apps.cmdb.models import AssetSource, AssetHost, AssetSyncRecord
    from apps.cmdb.tasks import sync_asset_source

    source = AssetSource.objects.create(
        code="review", name="review", source_type="cloud"
    )
    host = AssetHost.objects.create(
        hostname="review",
        internal_ip="10.0.0.9",
        asset_source=source,
        source_id="vm-1",
        connection_port=2222,
        owner_team="ops",
        environment="production",
        ansible_connection_vars={"custom": "kept"},
        metadata={"manual": "kept"},
    )
    record = AssetSyncRecord.objects.create(
        source=source,
        payload=[
            {
                "source_id": "vm-1",
                "hostname": "review-updated",
                "internal_ip": "10.0.0.10",
                "connection_port": 22,
                "metadata": {"provider": "cloud"},
            }
        ],
    )
    sync_asset_source(record.pk)
    host.refresh_from_db()
    assert host.connection_port == 2222
    assert host.owner_team == "ops"
    assert host.environment == "production"
    assert host.ansible_connection_vars == {"custom": "kept"}
    assert host.metadata == {"manual": "kept", "provider": "cloud"}
    assert host.hostname == "review-updated"
    assert host.internal_ip == "10.0.0.10"


@pytest.mark.django_db
def test_review_upload_respects_extension_config(actor, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.permission.models import SystemConfig
    from common.api.file_views import FileUploadApiView

    settings.MEDIA_ROOT = tmp_path
    SystemConfig.objects.create(
        config_key="file.upload.allowed_extensions",
        config_name="types",
        config_group="file",
        config_value="txt",
    )
    request = APIRequestFactory().post(
        "/api/v1/file/upload",
        {"file": SimpleUploadedFile("blocked.exe", b"demo")},
        format="multipart",
    )
    force_authenticate(request, actor)
    FileUploadApiView.as_view()(request)
    assert not list(tmp_path.rglob("*.exe"))


@pytest.mark.django_db
def test_review_password_obeys_configured_minimum(actor):
    from apps.permission.models import SystemConfig
    from apps.user.views.user_profile import UserProfileViewSet
    from rest_framework.test import APIRequestFactory, force_authenticate

    SystemConfig.objects.create(
        config_key="security.password.min_length",
        config_name="minimum",
        config_group="security",
        config_value="12",
    )
    request = APIRequestFactory().put(
        "/api/v1/users/password",
        {"oldPassword": "123456", "newPassword": "x"},
        format="json",
    )
    force_authenticate(request, actor)
    UserProfileViewSet.as_view({"put": "password"})(request)
    actor.refresh_from_db()
    assert not actor.check_password("x")


@pytest.mark.django_db
def test_upload_size_is_rejected_before_writing(actor, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.permission.models import SystemConfig
    from common.api.file_views import FileUploadApiView

    settings.MEDIA_ROOT = tmp_path
    SystemConfig.objects.create(
        config_key="file.upload.max_size_mb", config_name="size", config_value="1"
    )
    request = APIRequestFactory().post(
        "/api/v1/files",
        {"file": SimpleUploadedFile("large.txt", b"x" * (1024 * 1024 + 1))},
        format="multipart",
    )
    force_authenticate(request, actor)
    response = FileUploadApiView.as_view()(request)
    assert response.status_code == 400
    assert not list(tmp_path.rglob("*"))


@pytest.mark.django_db
def test_explicit_refresh_reports_cache_failure(actor, monkeypatch):
    from apps.permission.views.config import SystemConfigViewSet
    from rest_framework.test import APIRequestFactory, force_authenticate

    def offline(*args, **kwargs):
        raise ConnectionError("cache unavailable")

    monkeypatch.setattr("apps.permission.views.config.cache.set", offline)
    request = APIRequestFactory().put("/api/v1/configs/refresh", {}, format="json")
    force_authenticate(request, actor)
    response = SystemConfigViewSet.as_view({"put": "refresh"})(request)
    assert response.status_code == 503


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,method", [("create", "post"), ("password_reset", "put")]
)
def test_user_creation_and_admin_reset_enforce_password_minimum(actor, action, method):
    from django.contrib.auth import get_user_model
    from apps.permission.models import SystemConfig
    from apps.user.views.user_profile import UserProfileViewSet
    from rest_framework.test import APIRequestFactory, force_authenticate

    SystemConfig.objects.create(
        config_key="security.password.min_length",
        config_name="minimum",
        config_value="12",
    )
    count = get_user_model().objects.count()
    request = getattr(APIRequestFactory(), method)(
        f"/api/v1/users/{actor.pk}/password/reset"
        if action == "password_reset"
        else "/api/v1/users",
        {"username": "rejected-user", "password": "x"},
        format="json",
    )
    force_authenticate(request, actor)
    response = UserProfileViewSet.as_view({method: action})(
        request, **({"pk": actor.pk} if action == "password_reset" else {})
    )
    assert response.status_code == 400
    assert get_user_model().objects.count() == count
    actor.refresh_from_db()
    assert actor.check_password("123456")


@pytest.mark.django_db
def test_upload_accepts_exact_size_boundary_and_case_insensitive_extension(
    actor, settings, tmp_path
):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.permission.models import SystemConfig
    from common.api.file_views import FileUploadApiView

    settings.MEDIA_ROOT = tmp_path
    SystemConfig.objects.create(
        config_key="file.upload.max_size_mb", config_name="size", config_value="1"
    )
    SystemConfig.objects.create(
        config_key="file.upload.allowed_extensions",
        config_name="types",
        config_value=".txt",
    )
    request = APIRequestFactory().post(
        "/api/v1/files",
        {"file": SimpleUploadedFile("allowed.TXT", b"x" * 1024 * 1024)},
        format="multipart",
    )
    force_authenticate(request, actor)
    response = FileUploadApiView.as_view()(request)
    assert response.status_code == 200
    assert len(list(tmp_path.rglob("*.TXT"))) == 1
