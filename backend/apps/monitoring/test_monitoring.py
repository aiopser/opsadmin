from unittest.mock import Mock, patch

import pytest

from apps.consul.models import ConsulConnection
from apps.monitoring.models import MonitoringTarget, SyncRecord
from apps.monitoring.registration import (
    build_registration,
    enqueue_sync,
    run_sync,
    prometheus_config,
    recover_stale_syncs,
)
from apps.monitoring.serializers import MonitoringTargetSerializer
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.consul.client import ConsulError


@pytest.fixture
def target(db):
    connection = ConsulConnection.objects.create(
        name="local", endpoint="http://consul:8500"
    )
    return MonitoringTarget.objects.create(
        name="server", connection=connection, address="192.168.1.10", port=9100
    )


def test_registration_uses_stable_owned_id_and_preserves_labels(target):
    target.tags = ["prod"]
    target.meta = {"team": "ops"}
    payload = build_registration(target)
    assert payload["ID"] == target.service_id
    assert payload["Meta"]["managed_by"] == "devops-platform"
    assert payload["Meta"]["team"] == "ops"
    assert payload["Tags"] == ["prod"]
    assert "Check" not in payload


def test_reserved_meta_and_invalid_blackbox_target_rejected(target):
    serializer = MonitoringTargetSerializer(
        target, data={"meta": {"managed_by": "other"}}, partial=True
    )
    assert not serializer.is_valid()
    serializer = MonitoringTargetSerializer(
        target,
        data={"kind": "blackbox", "probe_target": "file:///etc/passwd"},
        partial=True,
    )
    assert not serializer.is_valid()


def test_blackbox_payload_and_prometheus_config(target):
    target.kind = "blackbox"
    target.probe_target = "https://example.com/health"
    target.probe_module = "http_2xx"
    payload = build_registration(target)
    assert payload["Meta"]["probe_target"] == target.probe_target
    assert "__param_target" in prometheus_config(target.connection)
    assert "private-token" not in prometheus_config(target.connection)


def test_generated_rules_and_discovery_preserve_consul_metadata(target):
    import yaml
    from apps.monitoring.registration import alert_rules

    config = yaml.safe_load(prometheus_config(target.connection))
    for job in config["scrape_configs"]:
        assert any(rule.get("action") == "labelmap" for rule in job["relabel_configs"])
    rules = yaml.safe_load(alert_rules(target.connection))["groups"][0]["rules"]
    assert any("probe_success" in rule["expr"] for rule in rules)
    assert all(rule["for"] == "5m" for rule in rules)


def test_prometheus_credentials_file_does_not_export_token(target):
    import yaml
    from apps.cmdb.crypto import encrypt_secret

    target.connection.token_encrypted = encrypt_secret("private-token")
    config_text = prometheus_config(target.connection)
    config = yaml.safe_load(config_text)
    for job in config["scrape_configs"]:
        sd = job["consul_sd_configs"][0]
        assert "token_file" not in sd
        assert sd["authorization"] == {
            "type": "Bearer",
            "credentials_file": "/etc/prometheus/secrets/consul.token",
        }
    assert "private-token" not in config_text


def test_sync_is_idempotent_and_refuses_foreign_instance(target):
    record = enqueue_sync(target.pk, "register")
    with pytest.raises(ValidationError):
        enqueue_sync(target.pk, "register")
    with patch("apps.monitoring.registration.ConsulClient") as client:
        client.return_value.agent_services.return_value = {
            target.service_id: {"Meta": {"managed_by": "foreign"}}
        }
        run_sync(record.pk)
        client.return_value.register.assert_not_called()
    record.refresh_from_db()
    assert record.status == "failed"
    assert "纳管" in record.error


def test_successful_register_then_deregister_is_recorded(target):
    with patch("apps.monitoring.registration.ConsulClient") as client:
        client.return_value.agent_services.return_value = {}
        record = enqueue_sync(target.pk, "register")
        run_sync(record.pk)
        target.refresh_from_db()
        assert target.registered is True
        client.return_value.register.assert_called_once()
        client.return_value.agent_services.return_value = {
            target.service_id: {
                "Meta": {"managed_by": "devops-platform", "target_id": str(target.pk)}
            }
        }
        record = enqueue_sync(target.pk, "deregister")
        run_sync(record.pk)
        target.refresh_from_db()
        assert target.registered is False
        assert SyncRecord.objects.filter(status="succeeded").count() == 2


def test_deregistered_target_can_be_deleted_without_losing_history(target):
    user = get_user_model().objects.create_superuser(
        username="monitor-admin", password="test-password"
    )
    record = SyncRecord.objects.create(
        target=target,
        operation="deregister",
        status="succeeded",
        target_name=target.name,
    )
    client = APIClient()
    client.force_authenticate(user)
    response = client.delete(f"/api/v1/monitoring/targets/{target.pk}")
    assert response.status_code == 200
    record.refresh_from_db()
    assert record.target_id is None
    assert record.target_name == "server"


def test_node_health_critical_overrides_passing_service_health(target):
    user = get_user_model().objects.create_superuser(
        username="health-admin", password="test-password"
    )
    client = APIClient()
    client.force_authenticate(user)
    with patch("apps.consul.views.ConsulClient") as consul:
        consul.return_value.agent_services.return_value = {
            "test": {"Service": "test", "Meta": {}}
        }
        consul.return_value.agent_checks.return_value = {
            "node": {"ServiceID": "", "Status": "critical"},
            "service": {"ServiceID": "test", "Status": "passing"},
        }
        response = client.get(
            f"/api/v1/consul/connections/{target.connection_id}/services"
        )
    assert response.data["data"][0]["health"] == "critical"


def test_failed_register_preserves_uncertainty_until_successful_deregister(target):
    with patch("apps.monitoring.registration.ConsulClient") as client:
        client.return_value.agent_services.return_value = {}
        client.return_value.register.side_effect = ConsulError("请求超时")
        record = enqueue_sync(target.pk, "register")
        run_sync(record.pk)
        target.refresh_from_db()
        assert target.registration_uncertain
        serializer = MonitoringTargetSerializer(
            target,
            data={
                "connection": ConsulConnection.objects.create(
                    name="other", endpoint="http://other:8500"
                ).pk
            },
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        with pytest.raises(ValidationError):
            serializer.save()
        record = enqueue_sync(target.pk, "deregister")
        run_sync(record.pk)
        target.refresh_from_db()
        assert not target.registration_uncertain


def test_stale_record_recovery_and_late_task_do_not_write(target):
    record = enqueue_sync(target.pk, "register")
    SyncRecord.objects.filter(pk=record.pk).update(
        updated_at=timezone.now() - timedelta(minutes=11)
    )
    assert recover_stale_syncs() == 1
    with patch("apps.monitoring.registration.ConsulClient") as client:
        run_sync(record.pk)
        client.assert_not_called()
    assert enqueue_sync(target.pk, "register").status == "queued"


def test_api_sync_preview_history_and_registered_delete_guard(target):
    user = get_user_model().objects.create_superuser(
        username="api-admin", password="test-password"
    )
    client = APIClient()
    client.force_authenticate(user)
    path = f"/api/v1/monitoring/targets/{target.pk}"
    assert client.get(path + "/preview").data["data"]["ID"] == target.service_id
    with patch("apps.monitoring.registration.ConsulClient") as consul:
        consul.return_value.agent_services.return_value = {}
        assert client.post(path + "/sync").status_code == 200
        assert client.delete(path).status_code == 400
        consul.return_value.agent_services.return_value = {
            target.service_id: {
                "Meta": {"managed_by": "devops-platform", "target_id": str(target.pk)}
            }
        }
        assert client.post(path + "/deregister").status_code == 200
    assert client.delete(path).status_code == 200
    assert SyncRecord.objects.filter(target__isnull=True).count() == 2


def test_unprivileged_user_cannot_access_new_routes(target):
    client = APIClient()
    user = get_user_model().objects.create_user(
        username="no-permissions", password="test-password"
    )
    client.force_authenticate(user)
    assert client.get("/api/v1/monitoring/targets").status_code == 403
    assert (
        client.post(f"/api/v1/monitoring/targets/{target.pk}/sync").status_code == 403
    )


def test_malformed_blackbox_url_is_validation_error(target):
    serializer = MonitoringTargetSerializer(
        target,
        data={"kind": "blackbox", "probe_target": "http://[invalid"},
        partial=True,
    )
    assert not serializer.is_valid()
    assert "probe_target" in serializer.errors
