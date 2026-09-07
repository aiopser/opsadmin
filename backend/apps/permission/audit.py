from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from django.forms.models import model_to_dict

from apps.permission.models import PermissionAccessLog, PermissionAuditLog


@dataclass
class AuditActor:
    user_id: Optional[int] = None
    username: str = ""


_audit_actor_ctx: ContextVar[AuditActor] = ContextVar(
    "permission_audit_actor",
    default=AuditActor(),
)


def set_audit_actor(user):
    if getattr(user, "is_authenticated", False):
        _audit_actor_ctx.set(
            AuditActor(
                user_id=getattr(user, "id", None),
                username=getattr(user, "username", ""),
            )
        )
    else:
        clear_audit_actor()


def clear_audit_actor():
    _audit_actor_ctx.set(AuditActor())


def get_audit_actor() -> AuditActor:
    return _audit_actor_ctx.get()


AUDIT_EXCLUDED_FIELDS = {"created_at", "updated_at"}


def serialize_instance(instance):
    field_names = [
        field.name
        for field in instance._meta.fields
        if field.name not in AUDIT_EXCLUDED_FIELDS
    ]
    data = model_to_dict(instance, fields=field_names)
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif hasattr(value, "pk"):
            data[key] = value.pk
    return data


def diff_snapshots(before, after):
    changes = {}
    keys = set(before) | set(after)
    for key in keys:
        old_value = before.get(key)
        new_value = after.get(key)
        if old_value != new_value:
            changes[key] = {"before": old_value, "after": new_value}
    return changes


def create_audit_log(*, action, instance, changes):
    actor = get_audit_actor()
    PermissionAuditLog.objects.create(
        actor_id=actor.user_id,
        actor_name=actor.username,
        action=action,
        target_type=instance._meta.label,
        target_id=str(instance.pk or ""),
        target_repr=str(instance),
        changes=changes or {},
    )


def create_relation_audit_log(*, action, model_label, target_id, target_repr, changes):
    actor = get_audit_actor()
    PermissionAuditLog.objects.create(
        actor_id=actor.user_id,
        actor_name=actor.username,
        action=action,
        target_type=model_label,
        target_id=str(target_id),
        target_repr=target_repr,
        changes=changes or {},
    )


def create_access_log(*, user, path, method, reason):
    PermissionAccessLog.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        actor_name=getattr(user, "username", "") if user else "",
        path=path,
        method=method,
        status=PermissionAccessLog.Status.DENIED,
        reason=reason,
    )
