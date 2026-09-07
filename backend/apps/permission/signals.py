from django.apps import apps
from django.db import connection
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_migrate,
    post_save,
    pre_save,
)
from django.dispatch import receiver

from apps.permission.audit import (
    create_audit_log,
    create_relation_audit_log,
    diff_snapshots,
    serialize_instance,
)
from apps.permission.models import Menu, Permission, PermissionAuditLog, Role
from apps.permission.services import sync_casbin_rules

USER_ROLE_SIGNALS_REGISTERED = False

_SEEDING = False


class suspend_permission_signals:
    """种子过程（init_system_settings）暂停权限同步与审计信号。

    种子会批量写入数百条 Permission/Menu/Role 及 M2M 绑定，若不暂停，
    每次写入都会触发一次全量 Casbin 规则重写与审计日志写入（O(N²) 放大）。
    seed_system_settings 结束时已统一调用一次 sync_casbin_rules()。
    """

    def __enter__(self):
        global _SEEDING
        _SEEDING = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _SEEDING
        _SEEDING = False
        return False


def _is_seeding():
    return _SEEDING


def _can_sync_permissions():
    user_model = apps.get_model("user", "UserProfile")
    required_tables = {
        Role._meta.db_table,
        Permission._meta.db_table,
        PermissionAuditLog._meta.db_table,
        user_model._meta.db_table,
        user_model.role.through._meta.db_table,
    }
    return required_tables.issubset(set(connection.introspection.table_names()))


def _sync_permissions():
    if apps.ready and _can_sync_permissions():
        sync_casbin_rules()


@receiver(post_migrate)
def sync_permissions_after_migrate(sender, app_config, **kwargs):
    if app_config and app_config.name == "apps.permission":
        _sync_permissions()


@receiver(pre_save, sender=Role)
@receiver(pre_save, sender=Permission)
@receiver(pre_save, sender=Menu)
def capture_pre_save_snapshot(sender, instance, **kwargs):
    if _is_seeding():
        return
    if instance.pk:
        old_instance = sender.objects.filter(pk=instance.pk).first()
        instance._audit_snapshot = (
            serialize_instance(old_instance) if old_instance else {}
        )
    else:
        instance._audit_snapshot = {}


@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
@receiver(post_save, sender=Permission)
@receiver(post_delete, sender=Permission)
def sync_permissions_on_model_change(sender, **kwargs):
    if _is_seeding():
        return
    _sync_permissions()


@receiver(post_save, sender=Role)
@receiver(post_save, sender=Permission)
@receiver(post_save, sender=Menu)
def audit_model_saved(sender, instance, created, **kwargs):
    if _is_seeding():
        return
    before = getattr(instance, "_audit_snapshot", {})
    after = serialize_instance(instance)
    action = (
        PermissionAuditLog.Action.CREATED
        if created
        else PermissionAuditLog.Action.UPDATED
    )
    changes = after if created else diff_snapshots(before, after)
    create_audit_log(action=action, instance=instance, changes=changes)


@receiver(post_delete, sender=Role)
@receiver(post_delete, sender=Permission)
@receiver(post_delete, sender=Menu)
def audit_model_deleted(sender, instance, **kwargs):
    if _is_seeding():
        return
    create_audit_log(
        action=PermissionAuditLog.Action.DELETED,
        instance=instance,
        changes=serialize_instance(instance),
    )


@receiver(m2m_changed, sender=Role.permission.through)
def sync_permissions_on_role_permission_change(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        if _is_seeding():
            return
        _sync_permissions()
        action_map = {
            "post_add": PermissionAuditLog.Action.RELATION_ADDED,
            "post_remove": PermissionAuditLog.Action.RELATION_REMOVED,
            "post_clear": PermissionAuditLog.Action.RELATION_CLEARED,
        }
        create_relation_audit_log(
            action=action_map[action],
            model_label="apps.permission.Role.permission",
            target_id=kwargs.get("instance").pk,
            target_repr=str(kwargs.get("instance")),
            changes={
                "permission_ids": sorted(list(kwargs.get("pk_set") or [])),
            },
        )


@receiver(m2m_changed, sender=Menu.permission.through)
def sync_menu_permission_change(sender, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        if _is_seeding():
            return
        _sync_permissions()
        action_map = {
            "post_add": PermissionAuditLog.Action.RELATION_ADDED,
            "post_remove": PermissionAuditLog.Action.RELATION_REMOVED,
            "post_clear": PermissionAuditLog.Action.RELATION_CLEARED,
        }
        create_relation_audit_log(
            action=action_map[action],
            model_label="apps.permission.Menu.permission",
            target_id=kwargs.get("instance").pk,
            target_repr=str(kwargs.get("instance")),
            changes={
                "permission_ids": sorted(list(kwargs.get("pk_set") or [])),
            },
        )


def register_user_role_signal():
    global USER_ROLE_SIGNALS_REGISTERED
    if USER_ROLE_SIGNALS_REGISTERED:
        return

    user_model = apps.get_model("user", "UserProfile")

    @receiver(post_save, sender=user_model)
    @receiver(post_delete, sender=user_model)
    def sync_permissions_on_user_change(sender, **kwargs):
        _sync_permissions()

    @receiver(m2m_changed, sender=user_model.role.through)
    def sync_permissions_on_user_role_change(sender, action, **kwargs):
        if action in {"post_add", "post_remove", "post_clear"}:
            if _is_seeding():
                return
            _sync_permissions()
            action_map = {
                "post_add": PermissionAuditLog.Action.RELATION_ADDED,
                "post_remove": PermissionAuditLog.Action.RELATION_REMOVED,
                "post_clear": PermissionAuditLog.Action.RELATION_CLEARED,
            }
            create_relation_audit_log(
                action=action_map[action],
                model_label="apps.user.UserProfile.role",
                target_id=kwargs.get("instance").pk,
                target_repr=str(kwargs.get("instance")),
                changes={
                    "role_ids": sorted(list(kwargs.get("pk_set") or [])),
                },
            )

    USER_ROLE_SIGNALS_REGISTERED = True
