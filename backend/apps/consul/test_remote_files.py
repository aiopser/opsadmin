import base64
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError


@pytest.fixture
def context(db):
    from apps.cmdb.models import AssetHost
    from apps.jobs.models import WorkerPool
    from .models import ConsulTemplateFile

    actor = get_user_model().objects.create_superuser(
        username="ct-reader", password="test"
    )
    host = AssetHost.objects.create(
        hostname="ct",
        internal_ip="192.168.10.9",
        os_family="linux",
        connection_type="ssh",
        connection_port=22,
    )
    WorkerPool.objects.create(
        code="ct-read", name="ct", queue_name="ansible.ct", is_default=True
    )
    template = ConsulTemplateFile.objects.create(
        name="example",
        host=host,
        path="/opt/consul-template/config/prometheus.hcl",
        content="draft",
    )
    return actor, host, template


def wire(content):
    raw = content.encode()
    return {
        "exists": True,
        "data": base64.b64encode(raw).decode(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }


@pytest.mark.django_db
def test_read_content_is_encrypted_and_diff_does_not_write_template(context):
    from apps.cmdb.crypto import decrypt_secret
    from .remote_files import schedule_read, execute_read, read_result, compare_read

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(actor, host.pk, template.path)

    def run(**kwargs):
        kwargs["on_event"](
            SimpleNamespace(
                event_type="host_ok",
                result={"stdout": json.dumps(wire('token = "private-value"\n'))},
            )
        )
        return SimpleNamespace(status="success")

    with patch("apps.consul.remote_files.execute_asset_module", side_effect=run):
        execute_read(record.pk)
    record.refresh_from_db()
    assert "private-value" not in record.content_encrypted
    assert "private-value" in decrypt_secret(record.content_encrypted)
    assert read_result(record, actor)["content"].startswith("token")
    assert compare_read(record, actor, "draft")["changed"] is True
    template.refresh_from_db()
    assert template.content == "draft"


@pytest.mark.django_db
@pytest.mark.parametrize("exists,content", [(False, None), (True, "")])
def test_missing_file_and_empty_file_are_distinct(context, exists, content):
    from .remote_files import schedule_read, execute_read, read_result

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(actor, host.pk, template.path)
    payload = (
        wire(content) if exists else {"exists": False, "sha256": "missing", "size": 0}
    )

    def run(**kwargs):
        kwargs["on_event"](
            SimpleNamespace(
                event_type="host_ok", result={"stdout": json.dumps(payload)}
            )
        )
        return SimpleNamespace(status="success")

    with patch("apps.consul.remote_files.execute_asset_module", side_effect=run):
        execute_read(record.pk)
    record.refresh_from_db()
    result = read_result(record, actor)
    assert result["exists"] is exists
    assert result["content"] == content


@pytest.mark.django_db
def test_read_denies_unrelated_user_and_revoked_permission(context):
    from .remote_files import schedule_read, read_result, execute_read

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(actor, host.pk, template.path)
    other = get_user_model().objects.create_superuser(username="other", password="test")
    with pytest.raises(PermissionDenied):
        read_result(record, other)
    with patch(
        "apps.consul.remote_files.verify_permission", return_value=(False, "denied")
    ), patch("apps.consul.remote_files.execute_asset_module") as run:
        execute_read(record.pk)
    run.assert_not_called()
    record.refresh_from_db()
    assert record.status == "failed"


@pytest.mark.django_db
def test_expired_read_cannot_authorize_deploy(context):
    from datetime import timedelta
    from .remote_files import schedule_read, deploy_baseline, template_revision

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(
            actor, host.pk, template.path, template.pk, template_revision(template)
        )
    record.expires_at = timezone.now() - timedelta(seconds=1)
    record.save()
    with pytest.raises(ValidationError):
        deploy_baseline(template, actor, record.pk)


@pytest.mark.django_db
def test_deploy_proof_binds_template_revision_and_host(context):
    from .remote_files import schedule_read, deploy_baseline, template_revision

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(
            actor, host.pk, template.path, template.pk, template_revision(template)
        )
    record.status, record.checksum, record.exists = "succeeded", "a" * 64, True
    record.save()
    assert deploy_baseline(template, actor, record.pk) == "a" * 64
    template.content = "changed-after-preview"
    template.save()
    with pytest.raises(ValidationError):
        deploy_baseline(template, actor, record.pk)


def test_deploy_script_checks_hash_before_replacement_and_restores_on_reload_error():
    from .templates import build_deploy_script

    script = build_deploy_script(
        "new",
        "/opt/consul-template/config/app.hcl",
        "systemctl reload consul-template",
        expected_checksum="a" * 64,
    )
    assert script.index("sha256sum") < script.index('mv -f "$tmp"')
    assert "cp -p" in script
    assert "restore" in script


@pytest.mark.parametrize(
    "command", ["systemctl reboot", "systemctl stop sshd", "pkill -9 sshd"]
)
def test_reload_cannot_control_unrelated_services(command):
    from .templates import validate_reload_command

    with pytest.raises(ValidationError):
        validate_reload_command(command)


@pytest.mark.django_db
def test_remote_api_round_trip_and_whitespace_preservation(context):
    from rest_framework.test import APIClient
    from .models import RemoteFileRead
    from .serializers import ConsulTemplateFileSerializer

    actor, host, template = context
    client = APIClient()
    client.force_authenticate(actor)
    with patch("apps.consul.remote_files.publish_read"):
        response = client.post(
            "/api/v1/consul/templates/read-remote",
            {"host": host.pk, "path": template.path},
            format="json",
        )
    assert response.status_code == 200, response.data
    read_id = response.data["data"]["id"]
    response = client.get(f"/api/v1/consul/templates/remote-reads/{read_id}")
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.data["data"]["content"] is None
    RemoteFileRead.objects.filter(pk=read_id).update(
        status="succeeded", exists=False, checksum="missing"
    )
    response = client.post(
        "/api/v1/consul/templates/compare-remote",
        {"read_id": read_id, "content": " new\n"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert "+ new" in response.data["data"]["diff"]
    serializer = ConsulTemplateFileSerializer(
        template, data={"content": " \nexample\n"}, partial=True
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().content == " \nexample\n"


@pytest.mark.django_db
def test_deploy_requires_fresh_preview_and_exposes_real_run_status(context):
    from rest_framework.test import APIClient
    from .remote_files import schedule_read, template_revision
    from .serializers import ConsulTemplateFileSerializer

    actor, host, template = context
    client = APIClient()
    client.force_authenticate(actor)
    assert (
        client.post(
            f"/api/v1/consul/templates/{template.pk}/deploy", {}, format="json"
        ).status_code
        == 400
    )
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(
            actor, host.pk, template.path, template.pk, template_revision(template)
        )
    record.status, record.exists, record.checksum = "succeeded", False, "missing"
    record.save()
    with patch("apps.consul.templates.enqueue_workflow_run"):
        response = client.post(
            f"/api/v1/consul/templates/{template.pk}/deploy",
            {"read_id": str(record.pk)},
            format="json",
        )
    assert response.status_code == 200, response.data
    template.refresh_from_db()
    assert template.last_deploy_run_id == response.data["data"]["run_id"]
    template.last_deploy_run.status = "failed"
    template.last_deploy_run.save(update_fields=["status"])
    assert (
        ConsulTemplateFileSerializer(template).data["last_deploy_status"] == "failure"
    )


@pytest.mark.django_db
def test_read_permission_is_distinct_from_deploy(context):
    from .remote_files import schedule_read

    actor, host, template = context
    with patch(
        "apps.consul.remote_files.verify_permission", return_value=(False, "denied")
    ):
        with pytest.raises(PermissionDenied):
            schedule_read(actor, host.pk, template.path)


@pytest.mark.django_db
def test_missing_expired_or_failed_result_cannot_be_compared(context):
    from .remote_files import schedule_read, compare_read

    actor, host, template = context
    with patch("apps.consul.remote_files.publish_read"):
        record = schedule_read(actor, host.pk, template.path)
    record.status = "failed"
    record.save()
    with pytest.raises(ValidationError):
        compare_read(record, actor, "draft")


@pytest.mark.parametrize("case", ["changed", "success", "reload_failed"])
def test_deploy_shell_keeps_changes_and_restores_original(tmp_path, case):
    import os
    from pathlib import Path
    import shutil
    import subprocess
    from .templates import build_deploy_script

    bash = (
        "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
    )
    if not bash or not Path(bash).exists():
        pytest.skip("shell smoke test needs bash")
    target = tmp_path / "app.hcl"
    assert target.resolve().is_relative_to(tmp_path.resolve())
    target.write_text("old", encoding="utf-8")
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    stub = binary_dir / "systemctl"
    stub.write_text(
        '#!/bin/sh\nif grep -q new "$CT_TEST_TARGET" && [ "$CT_TEST_FAIL" = 1 ]; then exit 1; fi\nexit 0\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(0o700)

    def posix(path):
        value = path.resolve().as_posix()
        return "/" + value[0].lower() + value[2:] if os.name == "nt" else value

    checksum = hashlib.sha256(b"old").hexdigest() if case != "changed" else "a" * 64
    script = build_deploy_script(
        "new",
        posix(target),
        "systemctl reload consul-template",
        expected_checksum=checksum,
    )
    started = tmp_path / "started"
    header = f"printf started > '{posix(started)}'\nexport PATH='{posix(binary_dir)}':$PATH\nexport CT_TEST_TARGET='{posix(target)}'\nexport CT_TEST_FAIL={'1' if case == 'reload_failed' else '0'}\n"
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-s"],
        input=header + script,
        text=True,
        capture_output=True,
        timeout=20,
        encoding="utf-8",
        errors="replace",
    )
    assert started.exists(), result.stderr
    assert target.read_text(encoding="utf-8") == (
        "new" if case == "success" else "old"
    ), result.stderr
    assert (result.returncode == 0) is (case == "success"), result.stderr
