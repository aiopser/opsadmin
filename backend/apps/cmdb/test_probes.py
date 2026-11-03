from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.models import AssetHost, AssetProbe
from apps.cmdb.probes import (
    PUBLISH_RETRY_AFTER_SECONDS,
    RUNNING_STALE_SECONDS,
    publish_asset_probe,
    recover_stale_probes,
    schedule_asset_probe,
)
from apps.cmdb.tasks import execute_asset_probe
from apps.cmdb.views import CredentialRefViewSet
from apps.jobs.models import WorkerPool
from apps.ops.contracts import RunnerResult


@pytest.fixture
def actor(user):
    user.is_superuser = True
    user.save()
    return user


@pytest.fixture
def pool():
    return WorkerPool.objects.create(
        code="main", name="Main", queue_name="q-module", is_default=True
    )


@pytest.fixture
def host():
    return AssetHost.objects.create(
        hostname="probe-target",
        internal_ip="192.0.2.30",
        os_family="linux",
        connection_type="ssh",
    )


def make_probe(host, pool=None, **overrides):
    fields = {
        "host": host,
        "triggered_by": None,
        "module": "ansible.builtin.ping",
        "worker_pool": pool,
    }
    fields.update(overrides)
    return AssetProbe.objects.create(**fields)


# --- scheduling -----------------------------------------------------------


@pytest.mark.django_db
def test_schedule_creates_pending_probe_routed_to_default_pool(actor, host, pool):
    probe = schedule_asset_probe(actor=actor, host_id=host.id)
    assert probe.status == AssetProbe.Status.PENDING
    assert probe.attempt == 0
    assert probe.kind == AssetProbe.Kind.CONNECT
    assert probe.module == "ansible.builtin.ping"
    assert probe.module_args == ""
    assert probe.timeout_seconds == 15
    assert probe.worker_pool_id == pool.id
    assert probe.triggered_by_id == actor.id


@pytest.mark.django_db
def test_schedule_uses_windows_module_for_winrm_host(actor, pool):
    host = AssetHost.objects.create(
        hostname="win-box",
        internal_ip="192.0.2.31",
        os_family="windows",
        connection_type="winrm",
    )
    probe = schedule_asset_probe(actor=actor, host_id=host.id)
    assert probe.module == "ansible.windows.win_ping"
    assert probe.module_args == ""


@pytest.mark.django_db
def test_schedule_facts_kind_uses_setup_module(actor, host, pool):
    probe = schedule_asset_probe(
        actor=actor, host_id=host.id, kind=AssetProbe.Kind.FACTS
    )
    assert probe.module == "ansible.builtin.setup"
    assert probe.module_args == "gather_subset=!all,!min,hardware,network"


@pytest.mark.django_db
def test_schedule_routes_probe_to_region_pool(actor, pool):
    region_pool = WorkerPool.objects.create(
        code="east", name="East", queue_name="q-east", region="cn-east"
    )
    host = AssetHost.objects.create(
        hostname="east-host",
        internal_ip="192.0.2.32",
        os_family="linux",
        connection_type="ssh",
        region="cn-east",
    )
    probe = schedule_asset_probe(actor=actor, host_id=host.id)
    assert probe.worker_pool_id == region_pool.id


@pytest.mark.django_db
def test_schedule_requires_host_access(user, host, pool):
    with pytest.raises(PermissionDenied):
        schedule_asset_probe(actor=user, host_id=host.id)
    assert AssetProbe.objects.count() == 0


@pytest.mark.django_db
def test_schedule_requires_worker_pool(actor, host):
    with pytest.raises(ValidationError):
        schedule_asset_probe(actor=actor, host_id=host.id)
    assert AssetProbe.objects.count() == 0


# --- publication ----------------------------------------------------------


@pytest.mark.django_db
def test_publish_delivers_pending_probe_to_pool_queue(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        assert publish_asset_probe(probe.id, probe.attempt) is True
    task.apply_async.assert_called_once_with(
        args=[probe.id, probe.attempt],
        queue="q-module",
        soft_time_limit=20,
        time_limit=25,
    )


@pytest.mark.django_db
def test_publish_skips_probe_already_claimed_by_worker(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    AssetProbe.objects.filter(pk=probe.pk).update(status=AssetProbe.Status.RUNNING)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        assert publish_asset_probe(probe.id, probe.attempt) is False
    task.apply_async.assert_not_called()


@pytest.mark.django_db
def test_publish_ignores_attempt_mismatch(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        assert publish_asset_probe(probe.id, probe.attempt + 1) is False
    task.apply_async.assert_not_called()


@pytest.mark.django_db
def test_publish_survives_broker_outage(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        task.apply_async.side_effect = RuntimeError("broker down")
        assert publish_asset_probe(probe.id, probe.attempt) is False
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.PENDING


# --- task claim and result recording --------------------------------------


@pytest.mark.django_db
def test_task_claim_fences_duplicate_delivery(user, host):
    probe = make_probe(host, triggered_by=user)
    claimed = AssetProbe.objects.filter(
        pk=probe.pk, attempt=probe.attempt, status=AssetProbe.Status.PENDING
    ).update(status=AssetProbe.Status.RUNNING)
    assert claimed == 1
    with patch("apps.cmdb.execution.execute_asset_module") as run:
        result = execute_asset_probe(probe.id, probe.attempt)
    assert result == {"probeId": probe.id, "claimed": False}
    run.assert_not_called()


@pytest.mark.django_db
def test_task_records_success(user, host):
    probe = make_probe(host, triggered_by=user)
    with patch(
        "apps.cmdb.execution.execute_asset_module",
        return_value=RunnerResult("success", 0),
    ) as run:
        result = execute_asset_probe(probe.id, probe.attempt)
    assert result["status"] == "success"
    run.assert_called_once()
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.SUCCESS
    assert probe.error == ""
    assert probe.result == {"runnerStatus": "success", "returnCode": 0, "error": ""}


@pytest.mark.django_db
def test_task_records_failed_runner_result(user, host):
    probe = make_probe(host, triggered_by=user)
    with patch(
        "apps.cmdb.execution.execute_asset_module",
        return_value=RunnerResult("failed", 2, {}, "connection refused"),
    ):
        result = execute_asset_probe(probe.id, probe.attempt)
    assert result["status"] == "failed"
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.FAILED
    assert probe.error == "connection refused"
    assert probe.result["runnerStatus"] == "failed"


@pytest.mark.django_db
def test_task_records_runner_exception(user, host):
    probe = make_probe(host, triggered_by=user)
    with patch(
        "apps.cmdb.execution.execute_asset_module",
        side_effect=RuntimeError("runner exploded"),
    ):
        result = execute_asset_probe(probe.id, probe.attempt)
    assert result["status"] == "failed"
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.FAILED
    assert probe.error == "runner exploded"


@pytest.mark.django_db
def test_task_reports_timeout_message(user, host):
    from celery.exceptions import SoftTimeLimitExceeded

    probe = make_probe(host, triggered_by=user)
    with patch(
        "apps.cmdb.execution.execute_asset_module",
        side_effect=SoftTimeLimitExceeded(),
    ):
        execute_asset_probe(probe.id, probe.attempt)
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.FAILED
    assert probe.error == "probe timed out"


@pytest.mark.django_db
def test_task_fails_probe_without_owner(host):
    probe = make_probe(host)
    result = execute_asset_probe(probe.id, probe.attempt)
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.FAILED
    assert probe.error == "probe owner was removed"


# --- recovery scanner ------------------------------------------------------


def _backdate(probe, seconds):
    AssetProbe.objects.filter(pk=probe.pk).update(
        updated_at=timezone.now() - timedelta(seconds=seconds)
    )


@pytest.mark.django_db
def test_recover_republishes_stale_pending(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    _backdate(probe, PUBLISH_RETRY_AFTER_SECONDS + 1)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        recovered = recover_stale_probes()
    assert recovered == 1
    task.apply_async.assert_called_once()
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.PENDING


@pytest.mark.django_db
def test_recover_leaves_fresh_pending_alone(actor, host, pool):
    probe = make_probe(host, pool=pool, triggered_by=actor)
    with patch("apps.cmdb.tasks.execute_asset_probe") as task:
        assert recover_stale_probes() == 0
    task.apply_async.assert_not_called()


@pytest.mark.django_db
def test_recover_fails_stale_running_probe(host):
    probe = make_probe(host, triggered_by=None)
    AssetProbe.objects.filter(pk=probe.pk).update(status=AssetProbe.Status.RUNNING)
    _backdate(probe, RUNNING_STALE_SECONDS + 1)
    assert recover_stale_probes() == 1
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.FAILED
    assert probe.error == "probe lost: worker did not report back"


@pytest.mark.django_db
def test_recover_leaves_fresh_running_alone(host):
    probe = make_probe(host, triggered_by=None)
    AssetProbe.objects.filter(pk=probe.pk).update(status=AssetProbe.Status.RUNNING)
    assert recover_stale_probes() == 0
    probe.refresh_from_db()
    assert probe.status == AssetProbe.Status.RUNNING


# --- API surface ------------------------------------------------------------


def _post_test_connection(request_user, host_id):
    factory = APIRequestFactory()
    request = factory.post(
        "/api/v1/cmdb/credential-refs/test-connection",
        {"hostId": host_id},
        format="json",
    )
    force_authenticate(request, user=request_user)
    return CredentialRefViewSet.as_view({"post": "test_connection"})(request)


def _get_probe_status(request_user, probe_id):
    factory = APIRequestFactory()
    request = factory.get(
        f"/api/v1/cmdb/credential-refs/probes/{probe_id}"
    )
    force_authenticate(request, user=request_user)
    # Bypass the view-level RBAC (covered by the permission module) so these
    # tests exercise the probe-specific owner checks in probe_status itself.
    with patch.object(CredentialRefViewSet, "permission_classes", []):
        return CredentialRefViewSet.as_view({"get": "probe_status"})(
            request, probe_id=str(probe_id)
        )


@pytest.mark.django_db
def test_api_test_connection_queues_probe(actor, host, pool):
    response = _post_test_connection(actor, host.id)
    assert response.status_code == 200
    probe = AssetProbe.objects.get()
    assert response.data["data"]["probeId"] == probe.id
    assert response.data["data"]["status"] == AssetProbe.Status.PENDING
    assert probe.module == "ansible.builtin.ping"
    assert probe.worker_pool_id == pool.id


@pytest.mark.django_db
def test_api_test_connection_requires_host_access(user, host, pool):
    response = _post_test_connection(user, host.id)
    assert response.status_code == 403
    assert AssetProbe.objects.count() == 0


@pytest.mark.django_db
def test_api_probe_status_visible_to_owner(user, host, pool):
    probe = make_probe(
        host,
        pool=pool,
        triggered_by=user,
        status=AssetProbe.Status.SUCCESS,
        result={"runnerStatus": "success", "returnCode": 0, "error": ""},
    )
    response = _get_probe_status(user, probe.id)
    assert response.status_code == 200
    assert response.data["data"]["status"] == "success"
    assert response.data["data"]["hostname"] == "probe-target"
    assert response.data["data"]["workerPoolName"] == "Main"


@pytest.mark.django_db
def test_api_probe_status_hides_other_users_probes(user, host, pool):
    other = get_user_model().objects.create_user(
        username="other", password="other-pass-123"
    )
    probe = make_probe(host, pool=pool, triggered_by=other)
    response = _get_probe_status(user, probe.id)
    assert response.status_code == 404


@pytest.mark.django_db
def test_api_probe_status_forbidden_for_inactive_user(host, pool):
    inactive = get_user_model().objects.create_user(
        username="suspended", password="suspended-pass-123", job_status=False
    )
    probe = make_probe(host, pool=pool, triggered_by=inactive)
    response = _get_probe_status(inactive, probe.id)
    assert response.status_code == 403
