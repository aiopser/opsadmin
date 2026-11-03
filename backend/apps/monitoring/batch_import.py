import hashlib
import json

from django.core import signing
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from apps.cmdb.models import AssetHost
from apps.consul.models import ConsulConnection
from apps.audit_center.services import create_domain_audit_event
from .models import MonitoringTarget, SyncRecord
from .registration import enqueue_sync
from .automatic import publish_records

SALT = "monitoring.host-import.v1"


class HostImportSerializer(serializers.Serializer):
    connection = serializers.PrimaryKeyRelatedField(
        queryset=ConsulConnection.objects.all()
    )
    host_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1, max_length=200
    )
    address_source = serializers.ChoiceField(
        choices=MonitoringTarget._meta.get_field("address_source").choices,
        default="internal",
    )
    port = serializers.IntegerField(min_value=1, max_value=65535, default=9100)
    sync_interval_minutes = serializers.IntegerField(
        min_value=0, max_value=10080, default=0
    )
    follow_host_address = serializers.BooleanField(default=False)

    def validate_host_ids(self, value):
        return sorted(set(value))


class HostImportCommitSerializer(HostImportSerializer):
    preview_token = serializers.CharField(max_length=1024)


def import_rows(data):
    connection = data["connection"]
    if not connection.is_active:
        raise serializers.ValidationError({"connection": "Consul 连接已停用"})
    hosts = {
        host.pk: host
        for host in AssetHost.objects.filter(pk__in=data["host_ids"]).order_by("pk")
    }
    rows, seen = [], set()
    for host_id in sorted(set(data["host_ids"])):
        host = hosts.get(host_id)
        address = (
            (
                host.internal_ip
                if data["address_source"] == "internal"
                else host.external_ip
            )
            if host
            else ""
        )
        action, reason = "create", "新建目标并提交注册"
        existing_ids = []
        if not host or host.status != "active" or not address:
            action, reason = "invalid", "主机不存在、已停用或缺少所选 IP"
        else:
            from .serializers import MonitoringTargetSerializer

            try:
                MonitoringTargetSerializer().validate_address(address)
            except serializers.ValidationError:
                action, reason = "invalid", "主机 IP 不允许用于监控"
            if action != "invalid":
                existing_ids = list(
                    MonitoringTarget.objects.filter(connection=connection, kind="host")
                    .filter(Q(host_id=host_id) | Q(address=address, port=data["port"]))
                    .order_by("pk")
                    .values_list("id", flat=True)
                )
                if existing_ids:
                    action, reason = "exists", "已有监控目标，保留原配置"
                elif address in seen:
                    action, reason = "duplicate", "所选主机 IP 重复，本次跳过"
                else:
                    seen.add(address)
        meta = {
            "asset_id": str(host_id),
            "asset_hostname": host.hostname if host else "",
            "asset_environment": host.environment if host else "",
            "asset_region": host.region if host else "",
        }
        rows.append(
            {
                "host_id": host_id,
                "name": host.hostname if host else f"主机 #{host_id}",
                "address": address or "",
                "action": action,
                "reason": reason,
                "existing_ids": existing_ids,
                "meta": meta,
            }
        )
    return rows


def digest(data, rows):
    config = {
        key: data[key]
        for key in (
            "host_ids",
            "address_source",
            "port",
            "sync_interval_minutes",
            "follow_host_address",
        )
    }
    config["connection"] = data["connection"].pk
    config["endpoint"] = data["connection"].endpoint
    return hashlib.sha256(
        json.dumps({"config": config, "rows": rows}, sort_keys=True).encode()
    ).hexdigest()


def preview_host_import(data, actor):
    rows = import_rows(data)
    token = signing.dumps({"actor": actor.pk, "digest": digest(data, rows)}, salt=SALT)
    return {
        "rows": rows,
        "preview_token": token,
        "create_count": sum(row["action"] == "create" for row in rows),
        "skip_count": sum(row["action"] != "create" for row in rows),
    }


def commit_host_import(data, actor, policy=None):
    try:
        proof = signing.loads(data["preview_token"], salt=SALT, max_age=600)
    except signing.BadSignature:
        raise serializers.ValidationError("预览已失效，请重新读取主机并预览") from None
    with transaction.atomic():
        connection = (
            ConsulConnection.objects.select_for_update()
            .filter(pk=data["connection"].pk)
            .first()
        )
        if not connection:
            raise serializers.ValidationError("连接已删除，请重新预览")
        data = {**data, "connection": connection}
        list(
            AssetHost.objects.select_for_update()
            .filter(pk__in=data["host_ids"])
            .order_by("pk")
        )
        rows = import_rows(data)
        if proof.get("actor") != actor.pk or proof.get("digest") != digest(data, rows):
            raise serializers.ValidationError("主机或目标配置已变化，请重新预览后确认")
        records, targets = [], []
        for row in rows:
            if row["action"] != "create":
                continue
            target = MonitoringTarget.objects.create(
                enrollment_policy=policy,
                name=row["name"],
                connection=connection,
                host_id=row["host_id"],
                kind="host",
                address=row["address"],
                port=data["port"],
                meta=row["meta"],
                address_source=data["address_source"],
                follow_host_address=data["follow_host_address"],
                sync_interval_minutes=data["sync_interval_minutes"],
                auto_sync_actor=actor if data["sync_interval_minutes"] else None,
            )
            records.append(
                enqueue_sync(target.pk, "register", actor, trigger="batch").pk
            )
            targets.append(target.pk)
        create_domain_audit_event(
            actor,
            "monitoring.host_import",
            "consul_connection",
            connection.pk,
            after={
                "target_ids": targets,
                "created": len(targets),
                "skipped": len(rows) - len(targets),
            },
            domain="monitoring",
        )
    if records:
        publish_records(records)
    return {
        "created": len(targets),
        "skipped": len(rows) - len(targets),
        "target_ids": targets,
        "delivery_failed": SyncRecord.objects.filter(
            pk__in=records, status="failed"
        ).count(),
    }
