import json
from unittest.mock import patch

import pytest

from .contracts import ProvisioningError


def test_private_artifacts_require_explicit_configuration(settings):
    from .terraform import ArtifactStore

    settings.PROVISIONING_ARTIFACT_ROOT = ""
    with pytest.raises(ProvisioningError, match="私有"):
        ArtifactStore()


def test_artifact_keys_cannot_escape_private_root(settings, tmp_path):
    from .terraform import ArtifactStore

    settings.PROVISIONING_ARTIFACT_ROOT = str(tmp_path)
    with pytest.raises(ProvisioningError):
        ArtifactStore().get("../secret")


def test_artifacts_are_encrypted_at_rest(settings, tmp_path):
    from .terraform import ArtifactStore

    settings.PROVISIONING_ARTIFACT_ROOT = str(tmp_path)
    store = ArtifactStore()
    key = store.put({"plan": "private-content"})
    assert b"private-content" not in (tmp_path / key).read_bytes()
    assert store.get(key)["plan"] == "private-content"


def test_runner_never_uses_shell_or_auto_approve(settings, tmp_path):
    from .terraform import TerraformRunner

    settings.PROVISIONING_TERRAFORM_BINARY = str(tmp_path / "terraform")
    settings.PROVISIONING_TERRAFORM_VERSION = "1.9.8"
    settings.PROVISIONING_CLI_CONFIG = str(tmp_path / "terraform.rc")
    (tmp_path / "terraform").touch()
    (tmp_path / "terraform.rc").touch()
    with patch("apps.provisioning.terraform.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({"terraform_version": "1.9.8"})
        runner = TerraformRunner(tmp_path, {})
        runner.command(["apply", "-input=false", "plan.bin"])
    args, kwargs = run.call_args
    assert args[0][-1] == "plan.bin"
    assert "-auto-approve" not in args[0]
    assert kwargs["shell"] is False
