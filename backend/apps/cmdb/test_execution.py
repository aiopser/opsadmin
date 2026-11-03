from pathlib import Path
from unittest.mock import patch

import pytest

from apps.cmdb.execution import execute_asset_module
from apps.cmdb.models import AssetHost, CredentialRef
from apps.ops.contracts import RunnerResult


@pytest.mark.django_db
@pytest.mark.parametrize("crash", [False, True])
def test_asset_probe_owns_key_lifetime(user, crash, settings):
    user.is_superuser = True
    user.save()
    settings.JOBS_CREDENTIAL_ENV_ALLOWLIST = ("ISOLATED_TEST_KEY",)
    credential = CredentialRef.objects.create(name="probe-key", type=CredentialRef.CredentialType.SSH_KEY,
        secret_ref="env:ISOLATED_TEST_KEY")
    host = AssetHost.objects.create(hostname="probe", internal_ip="192.0.2.10", credential_ref=credential,
        connection_type="ssh", os_family="linux")
    directories = []
    def execute(plan, on_event, should_cancel):
        directory = Path(plan.private_data_dir)
        directories.append(directory)
        keys = list(directory.glob("cred-*.key"))
        assert len(keys) == 1
        assert keys[0].read_text() == "isolated-test-key"
        assert "isolated-test-key" not in repr(plan)
        if crash:
            raise RuntimeError("fake runner crash")
        return RunnerResult("success", 0)
    with patch.dict("os.environ", {"ISOLATED_TEST_KEY": "isolated-test-key"}), patch(
        "apps.cmdb.execution.AnsibleExecutor.execute", side_effect=execute):
        if crash:
            with pytest.raises(RuntimeError, match="fake runner crash"):
                execute_asset_module(actor=user, host_id=host.id, module="ping", on_event=lambda event: None)
        else:
            assert execute_asset_module(actor=user, host_id=host.id, module="ping", on_event=lambda event: None).status == "success"
    assert len(directories) == 1
    assert not directories[0].exists()


@pytest.mark.django_db
def test_asset_probe_rejects_unauthorized_execution(user):
    from rest_framework.exceptions import PermissionDenied
    host = AssetHost.objects.create(hostname="probe", internal_ip="192.0.2.10", connection_type="ssh", os_family="linux")
    with patch("apps.cmdb.execution.AnsibleExecutor.execute") as execute:
        with pytest.raises(PermissionDenied):
            execute_asset_module(actor=user, host_id=host.id, module="ping", on_event=lambda event: None)
        execute.assert_not_called()
