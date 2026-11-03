import hashlib
import json
from datetime import timedelta

import yaml
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.consul.client import ConsulClient, ConsulError
from apps.consul.models import ConsulConnection
from apps.audit_center.services import create_domain_audit_event
from .models import MonitoringTarget, SyncRecord

ACTIVE = ["queued", "running"]


def recover_stale_syncs(target_id=None):
    rows = SyncRecord.objects.filter(
        status__in=ACTIVE, updated_at__lt=timezone.now() - timedelta(minutes=10)
    )
    if target_id is not None:
        rows = rows.filter(target_id=target_id)
    return rows.update(
        status="failed",
        error="同步任务长时间未完成，请检查 Worker；重新同步或注销以确认实际状态",
        finished_at=timezone.now(),
    )


def build_registration(target):
    meta = {
        **target.meta,
        "managed_by": "devops-platform",
        "target_id": str(target.pk),
        "kind": target.kind,
    }
    if target.kind == "blackbox":
        meta.update(probe_target=target.probe_target, probe_module=target.probe_module)
    payload = {
        "ID": target.service_id,
        "Name": "devops-" + target.kind,
        "Address": target.address,
        "Port": target.port,
        "Tags": target.tags,
        "Meta": meta,
    }
    if target.check_enabled:
        address = f"[{target.address}]" if ":" in target.address else target.address
        payload["Check"] = {
            "TCP": f"{address}:{target.port}",
            "Interval": "30s",
            "Timeout": "5s",
        }
    return payload


def revision(target):
    return hashlib.sha256(
        json.dumps(build_registration(target), sort_keys=True).encode()
    ).hexdigest()


@transaction.atomic
def enqueue_sync(target_id, operation, actor=None, trigger="manual"):
    if operation not in {"register", "deregister"}:
        raise ValidationError("无效的同步操作")
    if trigger not in {"manual", "batch", "automatic"}:
        raise ValidationError("无效的触发来源")
    connection_id = MonitoringTarget.objects.values_list(
        "connection_id", flat=True
    ).get(pk=target_id)
    connection = ConsulConnection.objects.select_for_update().get(pk=connection_id)
    target = MonitoringTarget.objects.select_for_update().get(pk=target_id)
    if target.connection_id != connection_id:
        raise ValidationError("目标连接已变更，请刷新后重试")
    if not connection.is_active:
        raise ValidationError("Consul 连接已停用，请先启用")
    recover_stale_syncs(target.pk)
    if target.sync_records.filter(status__in=ACTIVE).exists():
        raise ValidationError("目标正在同步，请勿重复提交")
    if operation == "deregister" and trigger == "manual":
        target.sync_interval_minutes = 0
        target.next_auto_sync_at = None
        target.auto_sync_actor = None
        target.save(
            update_fields=[
                "sync_interval_minutes",
                "next_auto_sync_at",
                "auto_sync_actor",
                "updated_at",
            ]
        )
    return SyncRecord.objects.create(
        target=target,
        target_name=target.name,
        operation=operation,
        actor=actor,
        trigger=trigger,
    )


def run_sync(record_id):
    with transaction.atomic():
        record = (
            SyncRecord.objects.select_for_update()
            .select_related("target__connection")
            .get(pk=record_id)
        )
        if record.status != "queued":
            return
        record.status = "running"
        record.save(update_fields=["status", "updated_at"])
    target = record.target
    error = ""
    try:
        if record.trigger == "automatic":
            from .automatic import check_auto_actor

            check_auto_actor(target, record.actor)
            if target.follow_host_address and (
                not target.host or target.host.status != "active"
            ):
                raise ConsulError("关联主机已删除或停用，已停止本次自动同步；原注册保留")
            if target.follow_host_address:
                selected_ip = (
                    target.host.internal_ip
                    if target.address_source == "internal"
                    else target.host.external_ip
                )
                if not selected_ip or selected_ip != target.address:
                    raise ConsulError("关联主机所选 IP 已缺失或变化，停止本次写入，等待下一轮同步")
        client = ConsulClient(target.connection)
        existing = client.agent_services().get(target.service_id)
        if existing is not None:
            meta = existing.get("Meta") or {}
            if meta.get("managed_by") != "devops-platform" or meta.get(
                "target_id"
            ) != str(target.pk):
                raise ConsulError("同 ID 服务未由本目标纳管，已拒绝覆盖或注销")
        if record.operation == "register":
            MonitoringTarget.objects.filter(pk=target.pk).update(
                registration_uncertain=True
            )
            client.register(build_registration(target))
        elif existing is not None:
            client.deregister(target.service_id)
    except (ConsulError, ValidationError) as exc:
        error = (
            "；".join(map(str, exc.detail))
            if isinstance(exc, ValidationError)
            else str(exc)
        )[:512]
    except Exception:
        error = "同步执行异常，请检查 Worker 状态后重试"
    with transaction.atomic():
        locked = SyncRecord.objects.select_for_update().get(pk=record_id)
        if locked.status != "running":
            return
        locked.status = "failed" if error else "succeeded"
        locked.error = error
        locked.finished_at = timezone.now()
        locked.save(update_fields=["status", "error", "finished_at", "updated_at"])
        if not error:
            MonitoringTarget.objects.filter(pk=target.pk).update(
                registered=record.operation == "register",
                registration_uncertain=False,
                synced_at=locked.finished_at,
                synced_revision=revision(target)
                if record.operation == "register"
                else "",
            )
        create_domain_audit_event(
            record.actor,
            "monitoring." + record.operation,
            "monitoring_target",
            target.pk,
            after={"record_id": record.pk, "error": error},
            domain="monitoring",
            result="failure" if error else "success",
        )


def prometheus_config(connection):
    from urllib.parse import urlsplit

    endpoint = urlsplit(connection.endpoint)
    discovery = {
        "server": endpoint.netloc,
        "scheme": endpoint.scheme,
        "services": ["devops-host", "devops-mysql", "devops-redis"],
    }
    if connection.datacenter:
        discovery["datacenter"] = connection.datacenter
    if connection.token_encrypted:
        discovery["authorization"] = {
            "type": "Bearer",
            "credentials_file": "/etc/prometheus/secrets/consul.token",
        }
    blackbox = {**discovery, "services": ["devops-blackbox"]}
    return yaml.safe_dump(
        {
            "scrape_configs": [
                {
                    "job_name": f"devops-consul-{connection.pk}",
                    "consul_sd_configs": [discovery],
                    "relabel_configs": [
                        {
                            "action": "labelmap",
                            "regex": "__meta_consul_service_metadata_(.+)",
                            "replacement": "consul_$1",
                        },
                        {
                            "source_labels": ["__meta_consul_tags"],
                            "target_label": "consul_tags",
                        },
                        {
                            "source_labels": [
                                "__meta_consul_service_metadata_managed_by"
                            ],
                            "regex": "devops-platform",
                            "action": "keep",
                        },
                        {
                            "source_labels": ["__meta_consul_service_id"],
                            "target_label": "instance",
                        },
                    ],
                },
                {
                    "job_name": f"devops-blackbox-{connection.pk}",
                    "metrics_path": "/probe",
                    "consul_sd_configs": [blackbox],
                    "relabel_configs": [
                        {
                            "action": "labelmap",
                            "regex": "__meta_consul_service_metadata_(.+)",
                            "replacement": "consul_$1",
                        },
                        {
                            "source_labels": ["__meta_consul_tags"],
                            "target_label": "consul_tags",
                        },
                        {
                            "source_labels": [
                                "__meta_consul_service_metadata_managed_by"
                            ],
                            "regex": "devops-platform",
                            "action": "keep",
                        },
                        {
                            "source_labels": [
                                "__meta_consul_service_metadata_probe_target"
                            ],
                            "target_label": "__param_target",
                        },
                        {
                            "source_labels": [
                                "__meta_consul_service_metadata_probe_module"
                            ],
                            "target_label": "__param_module",
                        },
                        {
                            "source_labels": ["__param_target"],
                            "target_label": "instance",
                        },
                    ],
                },
            ]
        },
        sort_keys=False,
        allow_unicode=True,
    )


def alert_rules(connection):
    rules = [
        {
            "alert": "DevopsExporterUnavailable",
            "expr": f'up{{job="devops-consul-{connection.pk}"}} == 0',
            "for": "5m",
            "labels": {"severity": "warning"},
            "annotations": {"summary": "Exporter 无法采集：{{ $labels.instance }}"},
        },
        {
            "alert": "DevopsBlackboxUnavailable",
            "expr": f'up{{job="devops-blackbox-{connection.pk}"}} == 0',
            "for": "5m",
            "labels": {"severity": "warning"},
            "annotations": {"summary": "Blackbox 采集失败：{{ $labels.instance }}"},
        },
        {
            "alert": "DevopsProbeFailed",
            "expr": f'probe_success{{job="devops-blackbox-{connection.pk}"}} == 0',
            "for": "5m",
            "labels": {"severity": "warning"},
            "annotations": {"summary": "站点探测失败：{{ $labels.instance }}"},
        },
    ]
    return yaml.safe_dump(
        {"groups": [{"name": f"devops-consul-{connection.pk}", "rules": rules}]},
        allow_unicode=True,
        sort_keys=False,
    )
