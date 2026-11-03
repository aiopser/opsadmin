import uuid
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.cmdb.models import AssetHost
from common.auth.rbac import verify_permission
from .models import JumpServerConnection, JumpServerMapping, JumpServerSync
from .client import JumpServerClient, JumpServerError


def authorized(actor, connection):
    return (
        actor
        and actor.is_active
        and getattr(actor, "job_status", False)
        and verify_permission(
            actor,
            f"/api/v1/integrations/jumpserver/connections/{connection.pk}/confirm",
            "POST",
        )[0]
    )


def host_payload(host, connection):
    if (
        host.status != "active"
        or host.connection_type != "ssh"
        or host.os_family not in {"linux", "windows"}
    ):
        raise ValidationError(
            f"主机 {host.pk} 仅支持 active SSH 资产；WinRM 不等同 RDP，请显式调整CMDB协议"
        )
    if not 1 <= host.connection_port <= 65535:
        raise ValidationError("主机端口无效")
    return {
        "name": host.hostname,
        "address": host.internal_ip,
        "platform": connection.windows_platform
        if host.os_family == "windows"
        else connection.linux_platform,
        "protocols": [{"name": "ssh", "port": host.connection_port}],
        "nodes": [connection.node_id],
        "is_active": True,
    }


@transaction.atomic
def preview(connection, actor, host_ids):
    connection = JumpServerConnection.objects.select_for_update().get(pk=connection.pk)
    if not connection.is_active or not authorized(actor, connection):
        raise ValidationError("连接停用或执行账号无权限")
    if (
        not isinstance(host_ids, list)
        or not host_ids
        or len(host_ids) > 500
        or len(set(host_ids)) != len(host_ids)
    ):
        raise ValidationError("请选择1至500台不同的CMDB主机")
    hosts = list(AssetHost.objects.filter(pk__in=host_ids).order_by("pk"))
    if len(hosts) != len(host_ids):
        raise ValidationError("主机不存在")
    snapshot = [
        {"host_id": host.pk, "payload": host_payload(host, connection)}
        for host in hosts
    ]
    return JumpServerSync.objects.create(
        connection=connection,
        actor=actor,
        snapshot=snapshot,
        connection_version=connection.updated_at,
        expires_at=timezone.now() + timedelta(minutes=10),
    )


@transaction.atomic
def confirm(run, actor):
    connection = JumpServerConnection.objects.select_for_update().get(
        pk=run.connection_id
    )
    run = JumpServerSync.objects.select_for_update().get(pk=run.pk)
    if run.actor_id != actor.pk or not authorized(actor, connection):
        raise ValidationError("仅有权限的预览创建者可确认")
    if (
        run.status != "preview"
        or run.expires_at < timezone.now()
        or run.connection_version != connection.updated_at
    ):
        raise ValidationError("预览过期、已确认或连接已修改，请重新预览")
    if connection.runs.filter(status__in=["queued", "running"]).exists():
        raise ValidationError("该连接已有同步任务")
    for item in run.snapshot:
        host = AssetHost.objects.filter(pk=item["host_id"]).first()
        if not host or host_payload(host, connection) != item["payload"]:
            raise ValidationError("主机已变化，请重新预览")
    run.status = "queued"
    run.save(update_fields=["status", "updated_at"])
    connection.selected_host_ids = [item["host_id"] for item in run.snapshot]
    connection.sync_actor = actor
    connection.save(update_fields=["selected_host_ids", "sync_actor"])
    return run


def execute(run_id):
    with transaction.atomic():
        run = (
            JumpServerSync.objects.select_for_update()
            .select_related("connection", "actor")
            .get(pk=run_id)
        )
        connection = JumpServerConnection.objects.select_for_update().get(
            pk=run.connection_id
        )
        if run.status != "queued":
            return
        if not connection.is_active or not authorized(run.actor, connection):
            run.status = "failed"
            run.error = "执行账号停用或权限已撤回"
            run.save()
            return
        run.status = "running"
        run.save()
    client = JumpServerClient(connection)
    results = []
    try:
        client.test()
        for item in run.snapshot:
            if not authorized(
                run.actor.__class__.objects.get(pk=run.actor_id), connection
            ):
                raise JumpServerError("执行权限已撤回")
            host = AssetHost.objects.filter(pk=item["host_id"]).first()
            if not host or host_payload(host, connection) != item["payload"]:
                raise JumpServerError("主机已变化，请重新预览")
            mapping, created = JumpServerMapping.objects.get_or_create(
                connection=connection, host=host, defaults={"external_id": uuid.uuid4()}
            )
            external_id = str(mapping.external_id)
            marker = f"CMDB:{connection.pk}:{host.pk}:{external_id}"
            payload = {**item["payload"], "comment": marker}
            # Reserve local identity before I/O; retries only update the exact owned UUID.
            remote = (
                None
                if created
                else client.request("GET", f"assets/hosts/{external_id}/")
            )
            if remote is None:
                result = client.request(
                    "POST", "assets/hosts/", {"id": external_id, **payload}
                )
                if str(result.get("id", "")) != external_id:
                    raise JumpServerError("远端未保留资产 UUID，停止同步并检查版本兼容性")
            else:
                if remote.get("comment") != marker:
                    raise JumpServerError("远端资产所有权标识不匹配，停止更新")
                client.request("PATCH", f"assets/hosts/{external_id}/", payload)
            results.append(
                {"host_id": host.pk, "external_id": external_id, "status": "succeeded"}
            )
        status = "succeeded"
        error = ""
    except JumpServerError as exc:
        status = "failed"
        error = str(exc)
    except Exception:
        status = "failed"
        error = "同步失败；请检查远端资产、网络、权限或主机变化后重新预览。未删除任何资产。"
    JumpServerSync.objects.filter(pk=run.pk).update(
        status=status, error=error, results=results, updated_at=timezone.now()
    )
    JumpServerConnection.objects.filter(pk=connection.pk).update(
        last_sync_at=timezone.now()
    )
