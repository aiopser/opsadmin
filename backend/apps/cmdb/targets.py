"""Single authorization and snapshot boundary for executable assets."""

from copy import deepcopy
import hashlib
import hmac
import json

from django.conf import settings
from django.db import transaction
from jsonschema import Draft202012Validator
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.auth.rbac import verify_permission
from .models import AssetHost, CredentialRef, HostGroup, HostTag, HostTagBinding
from .services import resolve_group_host_ids


VARIABLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ansible_user": {"type": "string"},
        "ansible_become": {"type": "boolean"},
        "ansible_become_user": {"type": "string"},
        "ansible_shell_type": {"enum": ["sh", "powershell", "cmd"]},
        "ansible_winrm_transport": {"enum": ["ntlm", "kerberos", "basic", "certificate", "credssp"]},
        "ansible_winrm_server_cert_validation": {"enum": ["validate", "ignore"]},
    },
}


def _authorize(actor, path: str) -> None:
    if not getattr(actor, "is_authenticated", False) or not actor.is_active or not getattr(actor, "job_status", True):
        raise PermissionDenied("Active actor required")
    if not verify_permission(actor, path, "GET")[0]:
        raise PermissionDenied("Target or credential access denied")


def _snapshot(actor, host: AssetHost) -> dict:
    _authorize(actor, f"/api/v1/cmdb/hosts/{host.pk}")
    if host.status != AssetHost.HostStatus.ACTIVE:
        raise ValidationError("Inactive target")
    if host.credential_ref_id:
        _authorize(actor, f"/api/v1/cmdb/credential-refs/{host.credential_ref_id}")
        if not host.credential_ref.is_active:
            raise ValidationError("Credential is disabled")
    variables = deepcopy(host.ansible_connection_vars or {})
    if not Draft202012Validator(VARIABLE_SCHEMA).is_valid(variables):
        raise ValidationError("Target variables contain unsupported or sensitive fields")
    if not 1 <= host.connection_port <= 65535:
        raise ValidationError("Invalid connection port")
    return {"host_id": host.pk, "hostname": host.hostname, "address": host.internal_ip,
            "port": host.connection_port, "connection_type": host.connection_type,
            "region": host.region,
            "credential_ref_id": host.credential_ref_id, "variables": variables}


def normalize_target_selector(*, host_ids=(), group_ids=(), tag_ids=()) -> dict:
    values = {"hostIds": host_ids, "groupIds": group_ids, "tagIds": tag_ids}
    if any(not isinstance(ids, (list, tuple)) for ids in values.values()):
        raise ValidationError("Target selectors must be identifier lists")
    if any(type(value) is not int or value <= 0 for ids in values.values() for value in ids):
        raise ValidationError("Target identifiers must be positive integers")
    return {key: sorted(set(ids)) for key, ids in values.items()}


def target_snapshot_fingerprint(targets) -> str:
    """Opaque confirmation digest; no connection details or credential references are exposed."""
    canonical = json.dumps(targets, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


@transaction.atomic
def resolve_targets(*, actor, host_ids, group_ids, tag_ids=()) -> list[dict]:
    selector = normalize_target_selector(host_ids=host_ids, group_ids=group_ids, tag_ids=tag_ids)
    host_ids = selector["hostIds"]
    group_ids = selector["groupIds"]
    tag_ids = selector["tagIds"]
    groups = HostGroup.objects.filter(pk__in=group_ids, is_active=True)
    if groups.count() != len(group_ids):
        raise ValidationError("Missing or inactive group")
    for group_id in group_ids:
        _authorize(actor, f"/api/v1/cmdb/host-groups/{group_id}")
    tags = HostTag.objects.filter(pk__in=tag_ids)
    if tags.count() != len(tag_ids):
        raise ValidationError("Target tag does not exist")
    for tag_id in tag_ids:
        _authorize(actor, f"/api/v1/cmdb/tags/{tag_id}")
    tagged_ids = set(HostTagBinding.objects.filter(tag_id__in=tag_ids).values_list("host_id", flat=True))
    selected_ids = set(host_ids) | resolve_group_host_ids(group_ids) | tagged_ids
    if not selected_ids:
        raise ValidationError("At least one target is required")
    hosts = list(AssetHost.objects.select_for_update().filter(pk__in=selected_ids).select_related("credential_ref").order_by("pk"))
    if len(hosts) != len(selected_ids):
        raise ValidationError("Target does not exist")
    return [_snapshot(actor, host) for host in hosts]


def snapshot_targets(*, actor, targets) -> list[dict]:
    # Never trust client snapshots or stale model instances: reload and authorize.
    ids = [target.pk if isinstance(target, AssetHost) else target["host_id"] for target in targets]
    return resolve_targets(actor=actor, host_ids=ids, group_ids=[])


@transaction.atomic
def authorize_frozen_targets(*, actor, targets) -> list[dict]:
    """Reauthorize stored targets without replacing their frozen connection data.

    Only server-owned run snapshots may enter this boundary. New runs from
    task definitions must continue to use snapshot_targets/resolve_targets.
    Credentials are checked by the original reference, not the current host binding.
    """
    ids = [target["host_id"] for target in targets]
    if any(type(host_id) is not int or host_id <= 0 for host_id in ids):
        raise ValidationError("Target identifiers must be positive integers")
    hosts = {
        host.pk: host
        for host in AssetHost.objects.select_for_update().filter(pk__in=ids)
    }
    if len(hosts) != len(set(ids)):
        raise ValidationError("Target does not exist")
    credential_ids = {
        target["credential_ref_id"] for target in targets
        if target.get("credential_ref_id") is not None
    }
    active_credential_ids = set(
        CredentialRef.objects.select_for_update().filter(
            pk__in=credential_ids, is_active=True
        ).values_list("pk", flat=True)
    )
    for target in targets:
        host = hosts[target["host_id"]]
        _authorize(actor, f"/api/v1/cmdb/hosts/{host.pk}")
        if host.status != AssetHost.HostStatus.ACTIVE:
            raise ValidationError("Inactive target")
        credential_id = target.get("credential_ref_id")
        if credential_id is not None:
            _authorize(actor, f"/api/v1/cmdb/credential-refs/{credential_id}")
            if credential_id not in active_credential_ids:
                raise ValidationError("Credential is missing or disabled")
        if not Draft202012Validator(VARIABLE_SCHEMA).is_valid(target.get("variables", {})):
            raise ValidationError("Target variables contain unsupported or sensitive fields")
        if type(target.get("port")) is not int or not 1 <= target["port"] <= 65535:
            raise ValidationError("Invalid connection port")
    return deepcopy(targets)
