from unittest.mock import Mock, patch

import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.consul.models import ConsulConnection, ConsulTemplateFile
from apps.consul.serializers import ConsulConnectionSerializer
from apps.consul.client import ConsulClient, ConsulError


@pytest.mark.django_db
def test_token_is_encrypted_hidden_and_blank_preserves_it():
    serializer = ConsulConnectionSerializer(
        data={
            "name": "test",
            "endpoint": "https://consul.example:8501",
            "token": "private-token",
        }
    )
    assert serializer.is_valid(), serializer.errors
    row = serializer.save()
    assert row.token_encrypted != "private-token"
    assert serializer.data["has_token"] is True
    assert "private-token" not in str(serializer.data)
    ciphertext = row.token_encrypted
    update = ConsulConnectionSerializer(row, data={"token": ""}, partial=True)
    assert update.is_valid(), update.errors
    assert update.save().token_encrypted == ciphertext


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://169.254.169.254:8500",
        "http://100.100.100.200",
        "http://[fd00:ec2::254]",
        "http://[::ffff:169.254.169.254]",
        "http://user:pass@consul:8500",
        "file:///tmp/consul",
        "https://consul:8501?token=secret",
    ],
)
@pytest.mark.django_db
def test_unsafe_consul_endpoint_is_rejected(endpoint):
    serializer = ConsulConnectionSerializer(data={"name": "bad", "endpoint": endpoint})
    assert not serializer.is_valid()
    assert "endpoint" in serializer.errors


@pytest.mark.django_db
def test_consul_client_timeout_and_error_do_not_expose_token():
    row = ConsulConnection.objects.create(
        name="safe", endpoint="https://consul.example:8501"
    )
    with patch("apps.consul.client.requests.Session") as session, patch(
        "apps.consul.client.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.10", 8501))],
    ):
        session.return_value.request.return_value = Mock(status_code=403)
        with pytest.raises(ConsulError, match="403"):
            ConsulClient(row).agent_services()
        assert session.return_value.trust_env is False
        assert session.return_value.request.call_args.kwargs["allow_redirects"] is False
        assert session.return_value.request.call_args.kwargs["timeout"] == (3, 10)


@pytest.mark.django_db
def test_new_routes_require_authentication():
    client = APIClient()
    assert client.get("/api/v1/consul/connections").status_code in (401, 403)
    user = get_user_model().objects.create_superuser(
        username="consul-admin", password="test-password"
    )
    client.force_authenticate(user)
    response = client.get("/api/v1/consul/connections")
    assert response.status_code == 200


@pytest.mark.django_db
def test_kv_key_validation_rejects_traversal_and_invalid_chars():
    row = ConsulConnection.objects.create(
        name="kv", endpoint="https://consul.example:8501"
    )
    client = ConsulClient(row)
    for bad_key in ["../secret", "a/../b", "a//b", "/abs", "with space", "a?", "a#b"]:
        with pytest.raises(ConsulError):
            client._check_kv_key(bad_key)
    with pytest.raises(ConsulError):
        client._check_kv_key("")
    assert client._check_kv_key("", allow_empty=True) == ""
    assert client._check_kv_key("IDC/") == "IDC/"
    assert client._check_kv_key("prometheus_config") == "prometheus_config"


@pytest.mark.django_db
def test_kv_keys_returns_sorted_and_treats_404_as_empty():
    row = ConsulConnection.objects.create(
        name="kv", endpoint="https://consul.example:8501"
    )
    with patch("apps.consul.client.requests.Session") as session, patch(
        "apps.consul.client.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.10", 8501))],
    ):
        session.return_value.request.return_value = Mock(
            status_code=200,
            content=b"[]",
            json=lambda: ["b/a", "a", "IDC/"],
        )
        assert ConsulClient(row).kv_keys() == ["IDC/", "a", "b/a"]
        session.return_value.request.return_value = Mock(
            status_code=404, content=b"", json=lambda: {}
        )
        assert ConsulClient(row).kv_keys("missing/") == []


@pytest.mark.django_db
def test_kv_value_decodes_base64_and_rejects_non_text():
    from base64 import b64encode

    row = ConsulConnection.objects.create(
        name="kv", endpoint="https://consul.example:8501"
    )
    encoded = b64encode('{"k": 1}'.encode()).decode()
    with patch("apps.consul.client.requests.Session") as session, patch(
        "apps.consul.client.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.10", 8501))],
    ):
        session.return_value.request.return_value = Mock(
            status_code=200,
            content=b"[]",
            json=lambda: [
                {
                    "Key": "test",
                    "Value": encoded,
                    "CreateIndex": 10,
                    "ModifyIndex": 20,
                    "LockIndex": 0,
                    "Flags": 0,
                }
            ],
        )
        assert ConsulClient(row).kv_value("test") == {
            "key": "test",
            "value": '{"k": 1}',
            "create_index": 10,
            "modify_index": 20,
            "lock_index": 0,
            "flags": 0,
        }
        session.return_value.request.return_value.json = lambda: [
            {"Key": "plain", "Value": encoded}
        ]
        assert ConsulClient(row).kv_value("plain")["modify_index"] == 0
        session.return_value.request.return_value.json = lambda: [
            {"Key": "bin", "Value": b64encode(b"\xff\xfe\x00").decode()}
        ]
        with pytest.raises(ConsulError, match="UTF-8"):
            ConsulClient(row).kv_value("bin")
        session.return_value.request.return_value.json = lambda: []
        with pytest.raises(ConsulError, match="不存在"):
            ConsulClient(row).kv_value("gone")


@pytest.mark.django_db
def test_kv_write_and_delete_guardrails():
    row = ConsulConnection.objects.create(
        name="kv", endpoint="https://consul.example:8501"
    )
    client = ConsulClient(row)
    with pytest.raises(ConsulError, match="目录"):
        client.kv_write("dir/", "x")
    with pytest.raises(ConsulError, match="1MB"):
        client.kv_write("big", "x" * (1024 * 1024 + 1))
    with pytest.raises(ConsulError, match="目录"):
        client.kv_delete("dir/")

    with patch("apps.consul.client.requests.Session") as session, patch(
        "apps.consul.client.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("192.168.1.10", 8501))],
    ):
        session.return_value.request.return_value = Mock(
            status_code=200, content=b"true", json=lambda: True
        )
        assert client.kv_write("prometheus_config", "scrape_configs: []") is True
        put_call = session.return_value.request.call_args
        assert (
            put_call.args[0] == "PUT"
            and put_call.kwargs["data"] == "scrape_configs: []"
        )
        assert client.kv_delete("prometheus_config") is True
        assert session.return_value.request.call_args.args[0] == "DELETE"
        session.return_value.request.return_value.json = lambda: False
        with pytest.raises(ConsulError, match="ACL"):
            client.kv_write("denied", "x")


@pytest.fixture
def template_host(db):
    from apps.cmdb.models import AssetHost

    return AssetHost.objects.create(
        hostname="ct-host",
        internal_ip="10.0.0.51",
        os_family=AssetHost.OSFamily.LINUX,
        connection_type="ssh",
        cpu_cores=2,
        memory_mb=4096,
        system_disk_gb=40,
    )


@pytest.mark.django_db
def test_template_routes_require_authentication():
    client = APIClient()
    assert client.get("/api/v1/consul/templates").status_code in (401, 403)
    assert client.post("/api/v1/consul/templates/1/deploy").status_code in (401, 403)


@pytest.mark.django_db
def test_template_path_and_reload_command_validation():
    from rest_framework.exceptions import ValidationError as DRFValidationError

    from apps.consul.templates import validate_reload_command, validate_template_path

    assert (
        validate_template_path("/etc/consul-template/conf.d/app.hcl")
        == "/etc/consul-template/conf.d/app.hcl"
    )
    for bad_path in ["etc/app.hcl", "/a/../b", "/ends/", "with space", "a;b"]:
        with pytest.raises(DRFValidationError):
            validate_template_path(bad_path)
    assert (
        validate_reload_command("systemctl  reload consul-template")
        == "systemctl reload consul-template"
    )
    assert validate_reload_command("") == ""
    for bad_command in [
        "rm -rf /",
        "echo hi; reboot",
        "kill $PID",
        "systemctl restart x && y",
        "sudo systemctl reload consul-template",
    ]:
        with pytest.raises(DRFValidationError):
            validate_reload_command(bad_command)


@pytest.mark.django_db
def test_deploy_script_and_source_version_requires_execution_risk_permission():
    from apps.automation.models import CommandAtom
    from apps.consul.templates import (
        build_deploy_script,
        ensure_deploy_source_version,
    )

    content = 'template {\n  source = "/etc/ct/app.ctmpl"\n}\n'
    script = build_deploy_script(
        content,
        "/etc/consul-template/conf.d/app.hcl",
        "systemctl reload consul-template",
    )
    assert "set -eu" in script
    assert "base64 -d" in script
    assert "systemctl reload consul-template" in script
    version = ensure_deploy_source_version(script)
    assert version.content == script
    assert version.command.risk_level == CommandAtom.RiskLevel.HIGH
    assert version.command.status == CommandAtom.Status.PUBLISHED
    assert ensure_deploy_source_version(script).pk == version.pk


@pytest.mark.django_db
def test_template_serializer_rejects_windows_host(db):
    from apps.cmdb.models import AssetHost
    from apps.consul.serializers import ConsulTemplateFileSerializer

    windows_host = AssetHost.objects.create(
        hostname="win-host",
        internal_ip="10.0.0.52",
        os_family=AssetHost.OSFamily.WINDOWS,
    )
    serializer = ConsulTemplateFileSerializer(
        data={
            "name": "win-template",
            "host": windows_host.pk,
            "path": "/etc/ct/w.hcl",
            "content": "",
        }
    )
    assert not serializer.is_valid()
    assert "host" in serializer.errors


@pytest.mark.django_db
def test_template_deploy_api_binds_remote_preview_and_risk(template_host):
    from apps.jobs.models import WorkerPool, WorkflowRun
    from .remote_files import schedule_read, template_revision

    WorkerPool.objects.create(
        code="ct", name="ct", queue_name="ansible.ct", is_default=True
    )
    user = get_user_model().objects.create_superuser(
        username="ct-admin", password="test-password"
    )
    row = ConsulTemplateFile.objects.create(
        name="prom",
        host=template_host,
        path="/etc/consul-template/conf.d/prom.hcl",
        content="template {}",
    )
    client = APIClient()
    client.force_authenticate(user)
    with patch("apps.consul.remote_files.publish_read"):
        read = schedule_read(
            user, template_host.pk, row.path, row.pk, template_revision(row)
        )
    read.status, read.exists, read.checksum = "succeeded", False, "missing"
    read.save()
    response = client.post(
        f"/api/v1/consul/templates/{row.pk}/deploy", {"read_id": str(read.pk)}
    )
    assert response.status_code == 200, response.content
    run = WorkflowRun.objects.get(pk=response.data["data"]["run_id"])
    assert run.name.startswith("模板下发-")
    assert run.input_vars["risk_level"] == "high"
    assert [target["host_id"] for target in run.target_snapshot] == [template_host.pk]
    row.refresh_from_db()
    assert row.last_deploy_status == "pending"
    assert "已提交" in row.last_deploy_message
