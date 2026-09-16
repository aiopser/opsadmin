import pytest

from apps.cmdb.models import AssetHost
from apps.cmdb.targets import snapshot_targets
from apps.cmdb.targets import resolve_targets
from apps.cmdb.models import CredentialRef, HostGroup, HostGroupMembership
from rest_framework.exceptions import PermissionDenied, ValidationError


@pytest.mark.django_db
def test_snapshot_uses_non_sensitive_target_contract(user):
    user.is_superuser = True
    user.save()
    host = AssetHost.objects.create(hostname="test-host", primary_ip="192.0.2.10", os_family="linux", connection_type="ssh")
    snapshot = snapshot_targets(actor=user, targets=[host])[0]
    assert set(snapshot) == {"host_id", "hostname", "address", "port", "connection_type", "region", "credential_ref_id", "variables"}
    assert snapshot["address"] == "192.0.2.10"


@pytest.fixture
def actor(user):
    user.is_superuser = True
    user.save()
    return user


@pytest.fixture
def host():
    return AssetHost.objects.create(hostname="safe", primary_ip="192.0.2.20", os_family="linux", connection_type="ssh")


@pytest.mark.django_db
def test_group_selection_deduplicates_and_resolves_dynamic_rules(actor, host):
    static = HostGroup.objects.create(name="static")
    HostGroupMembership.objects.create(group=static, host=host)
    dynamic = HostGroup.objects.create(name="dynamic", group_type="dynamic", match_rule={"os_family": "linux"})
    targets = resolve_targets(actor=actor, host_ids=[host.pk], group_ids=[static.pk, dynamic.pk])
    assert [target["host_id"] for target in targets] == [host.pk]


@pytest.mark.django_db
def test_snapshot_does_not_change_after_asset_edit(actor, host):
    snapshot = snapshot_targets(actor=actor, targets=[host])
    host.primary_ip = "192.0.2.21"
    host.save()
    assert snapshot[0]["address"] == "192.0.2.20"


@pytest.mark.django_db
def test_unauthorized_asset_is_rejected(user, host):
    with pytest.raises(PermissionDenied):
        resolve_targets(actor=user, host_ids=[host.pk], group_ids=[])


@pytest.mark.django_db
@pytest.mark.parametrize("host_ids,group_ids", [([], []), ([99999], []), ([], [99999])])
def test_missing_targets_and_groups_are_explicit(actor, host_ids, group_ids):
    with pytest.raises(ValidationError):
        resolve_targets(actor=actor, host_ids=host_ids, group_ids=group_ids)


@pytest.mark.django_db
def test_inactive_target_is_rejected(actor, host):
    host.status = "inactive"
    host.save()
    with pytest.raises(ValidationError):
        snapshot_targets(actor=actor, targets=[host])


@pytest.mark.django_db
def test_disabled_credential_and_secret_variables_are_rejected(actor, host):
    credential = CredentialRef.objects.create(name="disabled", type="password", scope="global", is_active=False)
    host.credential_ref = credential
    host.save()
    with pytest.raises(ValidationError):
        snapshot_targets(actor=actor, targets=[host])
    credential.is_active = True
    credential.save()
    host.ansible_connection_vars = {"ansible_password": "must-not-persist"}
    host.save()
    with pytest.raises(ValidationError):
        snapshot_targets(actor=actor, targets=[host])


@pytest.mark.django_db
def test_execution_rejects_credential_disabled_after_snapshot():
    from apps.cmdb.credentials import DatabaseCredentialProvider
    credential = CredentialRef.objects.create(name="disabled-at-execution", type="password", scope="global", is_active=False)
    with pytest.raises(ValueError, match="disabled"):
        DatabaseCredentialProvider().resolve(credential.pk)


@pytest.mark.django_db
def test_missing_credential_environment_variable_is_explicit(monkeypatch, settings):
    from apps.cmdb.credentials import DatabaseCredentialProvider
    monkeypatch.delenv("MISSING_PASSWORD", raising=False)
    settings.JOBS_CREDENTIAL_ENV_ALLOWLIST = ("MISSING_PASSWORD",)
    credential = CredentialRef.objects.create(
        name="env-ref", type="password", scope="global", secret_ref="env:MISSING_PASSWORD"
    )
    with pytest.raises(ValueError, match="is not configured"):
        DatabaseCredentialProvider().resolve(credential.pk)


@pytest.mark.django_db
def test_env_reference_is_rejected_when_disabled_by_default():
    from apps.cmdb.credentials import DatabaseCredentialProvider
    credential = CredentialRef.objects.create(
        name="env-ref", type="password", scope="global", secret_ref="env:ANY_PASSWORD"
    )
    with pytest.raises(ValueError, match="disabled"):
        DatabaseCredentialProvider().resolve(credential.pk)


@pytest.mark.django_db
def test_env_reference_outside_allowlist_is_rejected(settings):
    from apps.cmdb.credentials import DatabaseCredentialProvider
    settings.JOBS_CREDENTIAL_ENV_ALLOWLIST = ("OTHER_PASSWORD",)
    credential = CredentialRef.objects.create(
        name="env-ref", type="password", scope="global", secret_ref="env:MISSING_PASSWORD"
    )
    with pytest.raises(ValueError, match="allowlist"):
        DatabaseCredentialProvider().resolve(credential.pk)


@pytest.mark.django_db
def test_file_reference_outside_dedicated_directory_is_rejected(settings, tmp_path):
    from apps.cmdb.credentials import DatabaseCredentialProvider
    settings.JOBS_CREDENTIAL_FILE_DIR = str(tmp_path / "creds")
    outside = tmp_path / "elsewhere" / "id_rsa"
    credential = CredentialRef.objects.create(
        name="file-ref", type="ssh_key", scope="global", secret_ref=f"file:{outside}"
    )
    with pytest.raises(ValueError, match="inside the dedicated credential directory"):
        DatabaseCredentialProvider().resolve(credential.pk)


@pytest.mark.django_db
def test_vault_reference_is_rejected_at_execution():
    from apps.cmdb.credentials import DatabaseCredentialProvider
    credential = CredentialRef.objects.create(
        name="vault-ref", type="vault_ref", scope="global", secret_ref="vault://secret/data/db"
    )
    with pytest.raises(ValueError, match="not configured"):
        DatabaseCredentialProvider().resolve(credential.pk)
