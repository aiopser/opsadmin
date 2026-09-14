"""Single authorization and snapshot boundary for executable assets."""

from copy import deepcopy

from django.db import transaction
from jsonschema import Draft202012Validator
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.auth.rbac import verify_permission
from .models import AssetHost, HostGroup
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
        "gateway_ref_id": {"type": "integer", "minimum": 1},
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
    if host.default_gateway_id:
        variables["gateway_ref_id"] = host.default_gateway_id
    if not Draft202012Validator(VARIABLE_SCHEMA).is_valid(variables):
        raise ValidationError("Target variables contain unsupported or sensitive fields")
    if not 1 <= host.connection_port <= 65535:
        raise ValidationError("Invalid connection port")
    return {"host_id": host.pk, "hostname": host.hostname, "address": host.primary_ip,
            "port": host.connection_port, "connection_type": host.connection_type,
            "region": host.region,
            "credential_ref_id": host.credential_ref_id, "variables": variables}


@transaction.atomic
def resolve_targets(*, actor, host_ids, group_ids) -> list[dict]:
    host_ids, group_ids = set(host_ids), set(group_ids)
    if any(type(value) is not int or value <= 0 for value in host_ids | group_ids):
        raise ValidationError("Target identifiers must be positive integers")
    groups = HostGroup.objects.filter(pk__in=group_ids, is_active=True)
    if groups.count() != len(group_ids):
        raise ValidationError("Missing or inactive group")
    for group_id in group_ids:
        _authorize(actor, f"/api/v1/cmdb/host-groups/{group_id}")
    selected_ids = host_ids | resolve_group_host_ids(group_ids)
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
