"""Explicit-scope enrollment: create new targets, never modify/clean old ones."""
import hashlib
import json
from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.cmdb.models import AssetHost
from apps.cmdb.services import collect_group_tree_ids, resolve_group_host_ids
from apps.consul.models import ConsulConnection
from apps.audit_center.services import create_domain_audit_event
from common.auth.rbac import verify_permission
from .models import EnrollmentPolicy, EnrollmentRun, MonitoringTarget
from .serializers import MonitoringTargetSerializer
from .batch_import import preview_host_import, commit_host_import
from .registration import ACTIVE

SALT = "monitoring.enrollment.v1"
ALLOWED_RULES = {"os_family", "environment", "app_code", "asset_source"}


def validate_rules(rule):
    if not isinstance(rule, dict) or not rule or not set(rule).issubset(ALLOWED_RULES):
        raise ValidationError(
            "匹配规则必须为非空对象，仅支持 os_family、environment、app_code、asset_source"
        )
    for key, value in rule.items():
        values = value if isinstance(value, list) else [value]
        if not values or len(values) > 50:
            raise ValidationError("规则列表不能为空或超过 50 项")
        if key == "asset_source":
            if any(type(item) is not int or item <= 0 for item in values):
                raise ValidationError("asset_source 使用正整数资产来源 ID")
        elif any(
            not isinstance(item, str) or not item.strip() or len(item) > 128
            for item in values
        ):
            raise ValidationError("规则值必须是非空字符串")
        if key == "os_family" and not set(values).issubset({"linux", "windows"}):
            raise ValidationError("os_family 仅支持 linux、windows")


def actor_allowed(policy, actor):
    if (
        not actor
        or not actor.is_active
        or not getattr(actor, "job_status", False)
        or not verify_permission(
            actor, f"/api/v1/monitoring/enrollment-policies/{policy.pk}/run", "POST"
        )[0]
    ):
        raise ValidationError("执行账号失效或已无策略执行权限")
    if not verify_permission(actor, "/api/v1/cmdb/hosts", "GET")[0]:
        raise ValidationError("执行账号缺少资产读取权限")


def policy_snapshot(policy):
    if not policy.connection.is_active:
        raise ValidationError("Consul 连接已停用")
    hosts = AssetHost.objects.filter(status="active")
    if policy.scope == "group":
        if not policy.group_id or not policy.group or not policy.group.is_active:
            raise ValidationError("主机分组已删除或停用，不扩大为全部资产")
        ids = (
            collect_group_tree_ids([policy.group_id])
            if policy.include_descendants
            else [policy.group_id]
        )
        hosts = hosts.filter(pk__in=resolve_group_host_ids(ids))
    elif policy.scope == "rule":
        validate_rules(policy.match_rule)
        for key, value in policy.match_rule.items():
            hosts = (
                hosts.filter(**{key + "__in": value})
                if isinstance(value, list)
                else hosts.filter(**{key: value})
            )
    else:
        raise ValidationError("无效的纳管范围")
    matched = hosts.count()
    if matched > 10000:
        raise ValidationError("匹配范围超过 10000 台，请拆分分组或缩小规则")
    existing = list(
        MonitoringTarget.objects.filter(
            connection=policy.connection, kind="host"
        ).values("host_id", "address", "port")
    )
    host_ids = {item["host_id"] for item in existing if item["host_id"]}
    endpoints = {(item["address"], item["port"]) for item in existing}
    rows, seen = [], set()
    existing_count = invalid_count = remaining = 0
    for host in hosts.order_by("pk").iterator(chunk_size=500):
        address = (
            host.internal_ip
            if policy.address_source == "internal"
            else host.external_ip
        )
        if host.pk in host_ids or (address, policy.port) in endpoints:
            existing_count += 1
            continue
        try:
            if not address:
                raise ValidationError("缺少所选 IP")
            MonitoringTargetSerializer().validate_address(address)
        except ValidationError:
            invalid_count += 1
            continue
        if address in seen:
            invalid_count += 1
            continue
        seen.add(address)
        if len(rows) >= 200:
            remaining += 1
            continue
        rows.append(
            {
                "id": host.pk,
                "name": host.hostname,
                "address": address,
                "environment": host.environment,
                "region": host.region,
            }
        )
    values = {
        "policy": policy.pk,
        "updated_at": policy.updated_at.isoformat(),
        "endpoint": policy.connection.endpoint,
        "rows": rows,
        "matched": matched,
        "existing": existing_count,
        "invalid": invalid_count,
        "remaining": remaining,
    }
    digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return {
        "rows": rows,
        "matched_count": matched,
        "existing_count": existing_count,
        "invalid_count": invalid_count,
        "remaining_count": remaining,
        "create_count": len(rows),
        "digest": digest,
    }


def preview_policy(policy, actor):
    if (
        not actor
        or not actor.is_active
        or not getattr(actor, "job_status", False)
        or not verify_permission(actor, "/api/v1/cmdb/hosts", "GET")[0]
    ):
        raise ValidationError("预览账号缺少资产读取权限")
    snapshot = policy_snapshot(policy)
    snapshot["preview_token"] = signing.dumps(
        {"actor": actor.pk, "digest": snapshot["digest"]}, salt=SALT
    )
    return snapshot


def lock_policy(policy_id):
    connection_id = (
        EnrollmentPolicy.objects.filter(pk=policy_id)
        .values_list("connection_id", flat=True)
        .first()
    )
    if not connection_id:
        raise ValidationError("纳管策略已删除")
    ConsulConnection.objects.select_for_update().get(pk=connection_id)
    policy = (
        EnrollmentPolicy.objects.select_for_update()
        .select_related("connection", "group", "actor")
        .get(pk=policy_id)
    )
    if policy.connection_id != connection_id:
        raise ValidationError("策略连接已变更，请刷新")
    return policy


@transaction.atomic
def enqueue_policy_run(policy_id, actor, proof=None, automatic=False, enable=False):
    policy = lock_policy(policy_id)
    actor_allowed(policy, actor)
    if policy.runs.filter(status__in=ACTIVE).exists():
        raise ValidationError("策略正在执行，请勿重复提交")
    snapshot = policy_snapshot(policy)
    if not automatic:
        try:
            token = signing.loads(proof or "", salt=SALT, max_age=600)
        except signing.BadSignature:
            raise ValidationError("预览已过期，请重新预览") from None
        if token.get("actor") != actor.pk or token.get("digest") != snapshot["digest"]:
            raise ValidationError("范围或资产已变化，请重新预览")
    elif not policy.is_active:
        raise ValidationError("策略已暂停")
    if enable:
        policy.is_active = True
        policy.actor = actor
    policy.last_run_at = timezone.now()
    policy.next_run_at = policy.last_run_at + timedelta(minutes=policy.interval_minutes)
    policy.save(update_fields=["is_active", "actor", "last_run_at", "next_run_at"])
    return EnrollmentRun.objects.create(
        policy=policy,
        policy_name=policy.name,
        actor=actor,
        plan_digest=snapshot["digest"],
        trigger="automatic" if automatic else "manual",
    )


def execute_policy_run(run_id):
    with transaction.atomic():
        info = (
            EnrollmentRun.objects.filter(pk=run_id)
            .values("policy_id", "status")
            .first()
        )
        if not info or info["status"] != "queued":
            return
        if not info["policy_id"]:
            EnrollmentRun.objects.filter(pk=run_id).update(
                status="failed", error="策略已删除", finished_at=timezone.now()
            )
            return
        policy = lock_policy(info["policy_id"])
        run = EnrollmentRun.objects.select_for_update().get(pk=run_id)
        if run.status != "queued":
            return
        run.status = "running"
        run.save(update_fields=["status", "updated_at"])
    error, summary = "", {}
    try:
        actor_allowed(policy, run.actor)
        if (
            run.trigger == "automatic"
            and not EnrollmentPolicy.objects.filter(
                pk=policy.pk, is_active=True
            ).exists()
        ):
            raise ValidationError("策略已暂停，自动任务停止")
        snapshot = policy_snapshot(policy)
        if snapshot["digest"] != run.plan_digest:
            raise ValidationError("资产或范围在入队后变化，请重试；未创建目标")
        if snapshot["rows"]:
            values = {
                "connection": policy.connection,
                "host_ids": [row["id"] for row in snapshot["rows"]],
                "address_source": policy.address_source,
                "port": policy.port,
                "sync_interval_minutes": policy.target_sync_interval_minutes,
                "follow_host_address": policy.follow_host_address,
            }
            proof = preview_host_import(values, run.actor)
            summary = commit_host_import(
                {**values, "preview_token": proof["preview_token"]},
                run.actor,
                policy=policy,
            )
        else:
            summary = {"created": 0, "skipped": snapshot["matched_count"]}
        summary.update(
            matched=snapshot["matched_count"],
            remaining=snapshot["remaining_count"],
            invalid=snapshot["invalid_count"],
        )
    except ValidationError as exc:
        error = "；".join(map(str, exc.detail))[:512]
    except Exception:
        error = "策略执行失败，请检查 Worker、资产范围或队列状态"
    with transaction.atomic():
        updated = EnrollmentRun.objects.filter(pk=run_id, status="running").update(
            status="failed" if error else "succeeded",
            summary=summary,
            error=error,
            finished_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if updated:
            create_domain_audit_event(
                run.actor,
                "monitoring.enrollment.run",
                "enrollment_policy",
                policy.pk,
                after={"summary": summary, "error": error},
                result="failure" if error else "success",
                domain="monitoring",
            )


def publish_policy_run(run_id):
    from .tasks import execute_enrollment

    try:
        execute_enrollment.apply_async(args=[run_id], retry=False)
    except Exception:
        EnrollmentRun.objects.filter(pk=run_id, status="queued").update(
            status="failed", error="策略任务投递失败，请检查队列", finished_at=timezone.now()
        )


def dispatch_policies():
    EnrollmentRun.objects.filter(
        status__in=ACTIVE, updated_at__lt=timezone.now() - timedelta(minutes=15)
    ).update(status="failed", error="策略执行超时，请检查 Worker 后重试", finished_at=timezone.now())
    ids = list(
        EnrollmentPolicy.objects.filter(is_active=True)
        .filter(Q(next_run_at__isnull=True) | Q(next_run_at__lte=timezone.now()))
        .exclude(runs__status__in=ACTIVE)
        .values_list("pk", flat=True)[:30]
    )
    count = 0
    for policy_id in ids:
        policy = None
        try:
            with transaction.atomic():
                policy = lock_policy(policy_id)
                if not policy.is_active or (
                    policy.next_run_at and policy.next_run_at > timezone.now()
                ):
                    continue
                run = enqueue_policy_run(policy_id, policy.actor, automatic=True)
            publish_policy_run(run.pk)
            count += 1
        except ValidationError as exc:
            if (
                policy is None
                or not EnrollmentPolicy.objects.filter(pk=policy_id).exists()
            ):
                continue
            EnrollmentPolicy.objects.filter(pk=policy_id).update(is_active=False)
            EnrollmentRun.objects.create(
                policy_id=policy_id,
                policy_name=policy.name,
                actor=policy.actor,
                status="failed",
                trigger="automatic",
                error="；".join(map(str, exc.detail))[:512],
                plan_digest="",
                finished_at=timezone.now(),
            )
    return count
