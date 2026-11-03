from datetime import timedelta
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.auth.rbac import verify_permission
from .contracts import (
    ProvisioningError,
    canonical_digest,
    validate_inputs,
    validate_resource_scope,
)
from .models import (
    ProvisioningRequest,
    ProvisioningPlan,
    ProvisioningApproval,
    ProvisioningAttempt,
    ProvisioningEvent,
)


def authorize(actor, action, request_id):
    from django.contrib.auth import get_user_model

    actor = get_user_model().objects.filter(pk=getattr(actor, "pk", None)).first()
    if (
        not actor
        or not actor.is_active
        or not actor.job_status
        or not verify_permission(
            actor, f"/api/v1/provisioning/requests/{request_id}/{action}", "POST"
        )[0]
    ):
        raise ProvisioningError("无此操作权限")
    return actor


def snapshot(record):
    return {
        "version": record.version_id,
        "constraints": record.version.constraints,
        "provider": record.version.template.provider,
        "source": record.credential.source_id,
        "region": record.region,
        "parameters": record.parameters,
        "revision": record.revision,
        "stateGeneration": record.state_generation,
    }


def check_source(record):
    source = record.credential.source
    if (
        not source.is_active
        or not record.credential.is_active
        or not record.credential.encrypted_secret
    ):
        raise ProvisioningError("云账号或创建凭据未启用")
    if (
        source.source_type != "cloud"
        or source.cloud_provider not in {"aliyun", "tencent"}
        or source.cloud_provider != record.version.template.provider
    ):
        raise ProvisioningError("资源模板与云账号平台不一致")
    if (
        record.region not in source.regions
        or record.region not in record.version.constraints.get("regions", [])
    ):
        raise ProvisioningError("地域不在云账号和资源模板的允许范围内")
    if record.version.status != "published" or not record.version.template.is_active:
        raise ProvisioningError("资源模板未发布或已停用")


def check_credential_access(actor, record):
    from django.contrib.auth import get_user_model

    actor = (
        get_user_model()
        .objects.filter(pk=getattr(actor, "pk", None), is_active=True, job_status=True)
        .first()
    )
    if (
        actor is None
        or not verify_permission(
            actor,
            f"/api/v1/provisioning/credentials/{record.credential_id}/use",
            "POST",
        )[0]
    ):
        raise ProvisioningError("云账号创建凭据的使用权限已失效")


def check_approval(record, plan):
    if plan.confirmed_by_id != record.created_by_id:
        raise ProvisioningError("请由申请人确认计划")
    if (
        record.requires_approval
        and not plan.approvals.filter(decision="approved", digest=plan.digest)
        .exclude(actor_id=record.created_by_id)
        .exists()
    ):
        raise ProvisioningError("请等待审批通过")
    if record.approval_status not in {"approved", "not_required"}:
        raise ProvisioningError("审批尚未通过")


def current_plan(record, plan_id, digest):
    plan = ProvisioningPlan.objects.select_for_update().get(pk=plan_id, request=record)
    if (
        plan.status != "ready"
        or not secrets.compare_digest(plan.digest, digest)
        or plan.revision != record.revision
    ):
        raise ProvisioningError("计划已失效，请重新生成")
    if plan.expires_at <= timezone.now():
        raise ProvisioningError("计划已过期，请重新生成")
    if plan.credential_revision != record.credential.revision:
        raise ProvisioningError("凭据已变更，请重新生成计划")
    if plan.source_updated_at != record.credential.source.updated_at:
        raise ProvisioningError("云账号配置已变更，请重新生成计划")
    if plan.input_digest and plan.input_digest != canonical_digest(snapshot(record)):
        raise ProvisioningError("申请参数已变更，请重新生成计划")
    check_source(record)
    return plan


def locked_request(request_id):
    return (
        ProvisioningRequest.objects.select_for_update()
        .select_related("credential__source", "version__template")
        .get(pk=request_id)
    )


def event(record, actor, kind, message, plan=None, *, evidence=None):
    ProvisioningEvent.objects.create(
        request=record, actor=actor, kind=kind, message=message, plan=plan
    )
    from apps.audit_center.services import create_domain_audit_event

    create_domain_audit_event(
        actor,
        f"provisioning.{kind}",
        "provisioning_request",
        record.pk,
        after={
            "planId": plan.pk if plan else None,
            "message": message,
            **({"evidence": evidence} if evidence is not None else {}),
        },
        domain="task",
    )
    if kind in {"confirmed", "approved", "rejected"}:
        from .notifications import notify

        notify(record, kind, plan.pk if plan else None, message)


def dispatch(task, object_id, phase):
    try:
        task.apply_async(args=[object_id], queue="provisioning")
    except Exception:
        if phase == "plan":
            ProvisioningPlan.objects.filter(pk=object_id, status="queued").update(
                status="failed", error_message="任务投递失败，请检查专用 Worker 队列"
            )
        else:
            attempt = ProvisioningAttempt.objects.get(pk=object_id)
            if ProvisioningAttempt.objects.filter(pk=object_id, status="queued").update(
                status="failed", error_message="任务投递失败，请检查专用 Worker 队列"
            ):
                ProvisioningRequest.objects.filter(pk=attempt.plan.request_id).update(
                    execution_status="failed"
                )


@transaction.atomic
def queue_plan(request_id, actor):
    authorize(actor, "plan", request_id)
    record = locked_request(request_id)
    if record.created_by_id != actor.pk:
        raise ProvisioningError("仅申请人可生成计划")
    if (
        record.execution_status != "not_started"
        or record.plans.filter(status__in=["queued", "running"]).exists()
    ):
        raise ProvisioningError("已有执行或计划生成任务，请勿重复提交")
    check_source(record)
    check_credential_access(actor, record)
    validate_inputs(record.parameters, record.version.template.provider)
    validate_resource_scope(record)
    record.revision += 1
    record.approval_status = "pending"
    record.save(update_fields=["revision", "approval_status", "updated_at"])
    record.plans.filter(status="ready").update(status="superseded")
    plan = ProvisioningPlan.objects.create(
        request=record,
        revision=record.revision,
        credential_revision=record.credential.revision,
        source_updated_at=record.credential.source.updated_at,
        input_digest=canonical_digest(snapshot(record)),
        expires_at=timezone.now() + timedelta(minutes=30),
    )
    event(record, actor, "plan_queued", "已提交变更计划生成", plan)
    from .tasks import build_plan

    transaction.on_commit(lambda: dispatch(build_plan, plan.pk, "plan"))
    return plan


@transaction.atomic
def confirm_plan(request_id, actor, plan_id, digest):
    authorize(actor, "confirm", request_id)
    record = locked_request(request_id)
    if record.created_by_id != actor.pk:
        raise ProvisioningError("仅申请人可确认计划")
    plan = current_plan(record, plan_id, digest)
    if record.execution_status != "not_started":
        raise ProvisioningError("申请已进入执行阶段")
    plan.confirmed_by = actor
    plan.save(update_fields=["confirmed_by", "updated_at"])
    record.approval_status = "pending" if record.requires_approval else "not_required"
    record.save(update_fields=["approval_status", "updated_at"])
    event(record, actor, "confirmed", "已确认本次变更计划", plan)
    return record


@transaction.atomic
def approve_plan(request_id, actor, plan_id, digest, decision="approved", comment=""):
    authorize(actor, "approve" if decision == "approved" else "reject", request_id)
    record = locked_request(request_id)
    plan = current_plan(record, plan_id, digest)
    if actor.pk == record.created_by_id:
        raise ProvisioningError("不能审批本人申请")
    if (
        not plan.confirmed_by_id
        or record.execution_status != "not_started"
        or record.approval_status != "pending"
    ):
        raise ProvisioningError("计划尚未确认或已处理")
    if decision not in {"approved", "rejected"}:
        raise ProvisioningError("无效审批结果")
    ProvisioningApproval.objects.create(
        plan=plan,
        actor=actor,
        digest=plan.digest,
        decision=decision,
        comment=comment[:500],
    )
    record.approval_status = decision
    record.save(update_fields=["approval_status", "updated_at"])
    event(record, actor, decision, "审批通过" if decision == "approved" else "审批拒绝", plan)
    return record


@transaction.atomic
def execute_plan(request_id, actor, plan_id, digest, idempotency_key):
    authorize(actor, "execute", request_id)
    if not getattr(settings, "PROVISIONING_ENABLED", False):
        raise ProvisioningError("资源创建功能尚未启用，请先配置专用执行环境")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise ProvisioningError("请提交执行幂等键")
    record = locked_request(request_id)
    check_credential_access(actor, record)
    if record.created_by_id != actor.pk:
        raise ProvisioningError("仅申请人可执行已确认计划")
    existing = ProvisioningAttempt.objects.filter(
        plan_id=plan_id, plan__request=record
    ).first()
    if existing:
        if existing.idempotency_key != idempotency_key:
            raise ProvisioningError("该计划已有执行记录，请查看结果")
        return existing
    plan = current_plan(record, plan_id, digest)
    if not plan.confirmed_by_id or record.execution_status != "not_started":
        raise ProvisioningError("计划尚未确认或已执行")
    check_approval(record, plan)
    attempt = ProvisioningAttempt.objects.create(
        plan=plan, actor=actor, idempotency_key=idempotency_key
    )
    record.execution_status = "queued"
    record.save(update_fields=["execution_status", "updated_at"])
    event(record, actor, "execution_queued", "已提交资源创建", plan)
    from .tasks import apply_plan

    transaction.on_commit(lambda: dispatch(apply_plan, attempt.pk, "execute"))
    return attempt
