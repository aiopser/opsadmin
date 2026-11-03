from unittest.mock import patch
from types import SimpleNamespace
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.consul.client import ConsulClient
from apps.consul.models import ConsulConnection
from apps.cmdb.models import AssetHost
from apps.monitoring.models import MonitoringTarget, SyncRecord
from apps.monitoring.batch_import import preview_host_import, commit_host_import
from apps.monitoring.automatic import dispatch_due_targets
from apps.monitoring.registration import run_sync
from apps.monitoring.serializers import MonitoringTargetSerializer
from django.core import signing
from rest_framework.test import APIClient
import time


@pytest.fixture
def setup(db):
    user = get_user_model().objects.create_superuser(
        username="phase2-admin", password="test-password"
    )
    connection = ConsulConnection.objects.create(
        name="phase2", endpoint="http://consul:8500"
    )
    host = AssetHost.objects.create(
        hostname="node", internal_ip="192.168.10.1", os_family="linux"
    )
    return user, connection, host


def options(connection, host):
    return {
        "connection": connection,
        "host_ids": [host.pk],
        "address_source": "internal",
        "port": 9100,
        "sync_interval_minutes": 0,
        "follow_host_address": False,
    }


def test_catalog_uses_encoded_name_and_dc_without_agent_write(setup):
    _, connection, _ = setup
    client = ConsulClient(connection)
    with patch.object(client, "_request", return_value=[]) as request:
        assert client.catalog_instances("a/b ?", "dc-two") == []
    assert request.call_args.args[1] == "/health/service/a%2Fb%20%3F"
    assert request.call_args.kwargs["params"] == {"dc": "dc-two"}


def test_batch_preview_is_read_only_and_commit_is_idempotent(setup):
    user, connection, host = setup
    data = options(connection, host)
    preview = preview_host_import(data, user)
    assert preview["rows"][0]["action"] == "create"
    assert MonitoringTarget.objects.count() == 0
    with patch("apps.monitoring.batch_import.publish_records"):
        result = commit_host_import(
            {**data, "preview_token": preview["preview_token"]}, user
        )
    assert result["created"] == 1
    assert SyncRecord.objects.get().trigger == "batch"
    with pytest.raises(ValidationError):
        commit_host_import({**data, "preview_token": preview["preview_token"]}, user)
    next_preview = preview_host_import(data, user)
    assert next_preview["rows"][0]["action"] == "exists"


def test_batch_rejects_changed_asset_and_other_actor(setup):
    user, connection, host = setup
    data = options(connection, host)
    preview = preview_host_import(data, user)
    host.internal_ip = "192.168.10.2"
    host.save()
    with pytest.raises(ValidationError):
        commit_host_import({**data, "preview_token": preview["preview_token"]}, user)
    host.refresh_from_db()
    preview = preview_host_import(data, user)
    other = get_user_model().objects.create_superuser(
        username="other-admin", password="test-password"
    )
    with pytest.raises(ValidationError):
        commit_host_import({**data, "preview_token": preview["preview_token"]}, other)


def test_automatic_follows_selected_address_and_does_not_duplicate(setup):
    user, connection, host = setup
    target = MonitoringTarget.objects.create(
        name="auto",
        connection=connection,
        host=host,
        address="192.168.1.1",
        port=9100,
        sync_interval_minutes=5,
        follow_host_address=True,
        auto_sync_actor=user,
    )
    with patch("apps.monitoring.automatic.publish_records"):
        result = dispatch_due_targets()
        assert result["queued"] == 1
        assert dispatch_due_targets()["queued"] == 0
    target.refresh_from_db()
    assert target.address == host.internal_ip
    assert SyncRecord.objects.get().trigger == "automatic"


def test_automatic_revoked_actor_or_inactive_asset_never_unregisters(setup):
    user, connection, host = setup
    target = MonitoringTarget.objects.create(
        name="safe",
        connection=connection,
        host=host,
        address=host.internal_ip,
        registered=True,
        sync_interval_minutes=1,
        follow_host_address=True,
        auto_sync_actor=user,
    )
    user.is_active = False
    user.save()
    with patch("apps.monitoring.automatic.publish_records") as publish:
        assert dispatch_due_targets()["failed"] == 1
        publish.assert_not_called()
    target.refresh_from_db()
    assert target.registered
    assert SyncRecord.objects.get().operation == "register"


def test_missing_selected_public_address_is_not_replaced_with_private(setup):
    user, connection, host = setup
    preview = preview_host_import(
        {**options(connection, host), "address_source": "external"}, user
    )
    assert preview["rows"][0]["action"] == "invalid"


def test_auto_payload_edit_requires_sync_permission(setup):
    user, connection, host = setup
    target = MonitoringTarget.objects.create(
        name="auto",
        connection=connection,
        host=host,
        address=host.internal_ip,
        sync_interval_minutes=5,
        auto_sync_actor=user,
    )
    editor = get_user_model().objects.create_user(
        username="editor", password="test-password"
    )
    serializer = MonitoringTargetSerializer(
        target,
        data={"meta": {"team": "changed"}},
        partial=True,
        context={"request": SimpleNamespace(user=editor)},
    )
    with patch("common.auth.rbac.verify_permission", return_value=(False, "denied")):
        assert not serializer.is_valid()


def test_worker_rechecks_public_ip_after_automatic_dispatch(setup):
    user, connection, host = setup
    host.external_ip = "203.0.113.10"
    host.save()
    target = MonitoringTarget.objects.create(
        name="auto",
        connection=connection,
        host=host,
        address=host.external_ip,
        sync_interval_minutes=5,
        follow_host_address=True,
        address_source="external",
        auto_sync_actor=user,
    )
    with patch("apps.monitoring.automatic.publish_records"):
        dispatch_due_targets()
    record = SyncRecord.objects.get(target=target)
    host.external_ip = None
    host.save()
    with patch("apps.monitoring.registration.ConsulClient") as client:
        run_sync(record.pk)
        client.assert_not_called()
    record.refresh_from_db()
    assert record.status == "failed"


def test_manual_deregister_pauses_automatic_sync(setup):
    from apps.monitoring.registration import enqueue_sync

    user, connection, host = setup
    target = MonitoringTarget.objects.create(
        name="auto",
        connection=connection,
        host=host,
        address=host.internal_ip,
        sync_interval_minutes=5,
        auto_sync_actor=user,
    )
    enqueue_sync(target.pk, "deregister", user)
    target.refresh_from_db()
    assert target.sync_interval_minutes == 0
    assert target.auto_sync_actor_id is None


def test_expired_preview_is_rejected_without_creation(setup):
    user, connection, host = setup
    data = options(connection, host)
    with patch(
        "django.core.signing.TimestampSigner.timestamp",
        return_value=signing.b62_encode(int(time.time()) - 601),
    ):
        preview = preview_host_import(data, user)
    with pytest.raises(ValidationError):
        commit_host_import({**data, "preview_token": preview["preview_token"]}, user)
    assert not MonitoringTarget.objects.exists()


def test_periodic_sync_permission_revocation_disables_it(setup):
    user, connection, host = setup
    target = MonitoringTarget.objects.create(
        name="revoked",
        connection=connection,
        host=host,
        address=host.internal_ip,
        sync_interval_minutes=5,
        auto_sync_actor=user,
    )
    with patch(
        "apps.monitoring.automatic.verify_permission", return_value=(False, "revoked")
    ), patch("apps.monitoring.automatic.publish_records") as publish:
        assert dispatch_due_targets()["failed"] == 1
        publish.assert_not_called()
    target.refresh_from_db()
    assert target.sync_interval_minutes == 0
    assert "ErrorDetail" not in SyncRecord.objects.get().error


def test_catalog_instances_are_paginated_and_read_only(setup):
    user, connection, _ = setup
    client = APIClient()
    client.force_authenticate(user)
    item = {
        "Node": {"Node": "other-node", "Address": "192.168.2.2"},
        "Service": {
            "ID": "same-id",
            "Service": "web",
            "Address": "",
            "Port": 80,
            "Meta": {"managed_by": "devops-platform"},
        },
        "Checks": [{"Status": "critical"}, {"Status": "passing"}],
    }
    with patch("apps.consul.views.ConsulClient") as consul:
        consul.return_value.catalog_instances.return_value = [item]
        response = client.get(
            f"/api/v1/consul/connections/{connection.pk}/catalog-instances",
            {"service": "web", "datacenter": "dc2", "pageNum": 1, "pageSize": 1},
        )
    assert response.status_code == 200
    assert response.data["data"]["total"] == 1
    row = response.data["data"]["list"][0]
    assert row["managed"] is False
    assert row["health"] == "critical"
    assert row["address"] == "192.168.2.2"


def test_busy_targets_do_not_starve_other_due_targets(setup):
    user, connection, host = setup
    for index in range(100):
        target = MonitoringTarget.objects.create(
            name=f"busy-{index}",
            connection=connection,
            address=host.internal_ip,
            sync_interval_minutes=1,
            auto_sync_actor=user,
        )
        SyncRecord.objects.create(target=target, operation="register", status="queued")
    available = MonitoringTarget.objects.create(
        name="available",
        connection=connection,
        address=host.internal_ip,
        sync_interval_minutes=1,
        auto_sync_actor=user,
    )
    with patch("apps.monitoring.automatic.publish_records"):
        assert dispatch_due_targets()["queued"] == 1
    assert SyncRecord.objects.filter(target=available).exists()
