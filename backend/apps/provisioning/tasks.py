"""Dedicated delivery workers. A claimed apply is never automatically replayed."""
from datetime import timedelta
from pathlib import Path
import tempfile
import shutil

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .contracts import ProvisioningError, canonical_digest, summarize_plan
from .models import ProvisioningPlan, ProvisioningAttempt, ProvisioningRequest
from .services import (
    snapshot,
    check_source,
    check_credential_access,
    check_approval,
    current_plan,
    authorize,
    event,
)
from .terraform import (
    ArtifactStore,
    TerraformRunner,
    credential_environment,
    prepare_bundle,
    archive_workspace,
    restore_workspace,
)


@shared_task(name="provisioning.build_plan")
def build_plan(plan_id):
    if not ProvisioningPlan.objects.filter(pk=plan_id, status="queued").update(
        status="running", updated_at=timezone.now()
    ):
        return
    plan = ProvisioningPlan.objects.select_related(
        "request__credential__source",
        "request__version__template",
        "request__created_by",
    ).get(pk=plan_id)
    from .worker_health import claim_lease, lease_callback

    token = claim_lease("plan", plan_id)
    try:
        record = plan.request
        record.created_by = authorize(record.created_by, "plan", record.pk)
        check_credential_access(record.created_by, record)
        check_source(record)
        from .catalog.validation import resolve_request_resources

        resources = resolve_request_resources(record, record.created_by, refresh=True)
        from .state_protection import assert_write_protected

        assert_write_protected(record)
        if (
            plan.input_digest != canonical_digest(snapshot(record))
            or plan.credential_revision != record.credential.revision
            or plan.source_updated_at != record.credential.source.updated_at
        ):
            raise ProvisioningError("申请或账号已变更，请重新生成计划")
        store = ArtifactStore()
        with tempfile.TemporaryDirectory(
            prefix=f"plan-{plan_id}-", dir=store.working_root
        ) as directory:
            workspace = Path(directory)
            prepare_bundle(record, workspace)
            runner = TerraformRunner(
                workspace,
                credential_environment(record),
                on_tick=lease_callback("plan", plan_id, token),
            )
            runner.initialize()
            record.created_by = authorize(record.created_by, "plan", record.pk)
            check_credential_access(record.created_by, record)
            summary = summarize_plan(runner.plan(), record.version.template.provider)
            if len(summary) != record.parameters["count"]:
                raise ProvisioningError("计划主机数量与申请数量不一致")
            files = archive_workspace(workspace)
            digest = canonical_digest(
                {
                    "files": files,
                    "inputs": plan.input_digest,
                    "credential_revision": plan.credential_revision,
                    "terraform": runner.version,
                    **({"resources": resources} if resources else {}),
                }
            )
            key = store.put(
                {"files": files, "digest": digest, "terraform": runner.version}
            )
        updated = ProvisioningPlan.objects.filter(
            pk=plan_id, status="running", execution_token=token
        ).update(
            status="ready",
            digest=digest,
            artifact_key=key,
            summary=summary,
            resource_snapshot=resources,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        if not updated:
            return
        from .models import ProvisioningArtifact

        ProvisioningArtifact.objects.create(
            request=record,
            purpose="plan",
            key=key,
            digest=canonical_digest(files),
            key_id=getattr(settings, "PROVISIONING_STATE_ACTIVE_KEY_ID", ""),
            expires_at=timezone.now() + timedelta(days=30),
        )
        event(record, record.created_by, "plan_ready", "变更计划已生成，可确认影响范围", plan)
    except Exception as exc:
        message = (
            str(exc) if isinstance(exc, ProvisioningError) else "变更计划生成失败，请检查专用执行环境配置"
        )
        ProvisioningPlan.objects.filter(
            pk=plan_id, status="running", execution_token=token
        ).update(status="failed", error_message=message)
        event(plan.request, plan.request.created_by, "plan_failed", message, plan)


@shared_task(name="provisioning.apply_plan", acks_late=False)
def apply_plan(attempt_id):
    with transaction.atomic():
        attempt = (
            ProvisioningAttempt.objects.select_for_update()
            .select_related(
                "actor",
                "plan__request__credential__source",
                "plan__request__version__template",
            )
            .get(pk=attempt_id)
        )
        if attempt.status != "queued":
            return
        record = ProvisioningRequest.objects.select_for_update().get(
            pk=attempt.plan.request_id
        )
        attempt.status = "running"
        attempt.started_at = timezone.now()
        attempt.save(update_fields=["status", "started_at", "updated_at"])
        record.execution_status = "running"
        record.save(update_fields=["execution_status", "updated_at"])
    applied = False
    from .worker_health import claim_lease, lease_callback

    token = claim_lease("attempt", attempt_id)
    try:
        if not getattr(settings, "PROVISIONING_ENABLED", False):
            raise ProvisioningError("资源创建功能未启用")
        record = attempt.plan.request
        from .state_protection import assert_write_protected, capture_state

        assert_write_protected(record)
        attempt.actor = authorize(attempt.actor, "execute", record.pk)
        check_credential_access(attempt.actor, record)
        from .catalog.validation import validate_resolved_resources

        validate_resolved_resources(record, attempt.actor)
        with transaction.atomic():
            current_plan(record, attempt.plan_id, attempt.plan.digest)
            check_approval(record, attempt.plan)
        store = ArtifactStore()
        saved = store.get(attempt.plan.artifact_key)
        expected = canonical_digest(
            {
                "files": saved["files"],
                "inputs": attempt.plan.input_digest,
                "credential_revision": attempt.plan.credential_revision,
                "terraform": saved["terraform"],
                **(
                    {"resources": attempt.plan.resource_snapshot}
                    if attempt.plan.resource_snapshot
                    else {}
                ),
            }
        )
        if expected != attempt.plan.digest or saved["digest"] != expected:
            raise ProvisioningError("保存计划完整性校验失败")
        workspace = Path(
            tempfile.mkdtemp(prefix=f"attempt-{attempt_id}-", dir=store.working_root)
        )
        persisted = False
        try:
            restore_workspace(saved["files"], workspace)
            runner = TerraformRunner(
                workspace,
                credential_environment(record),
                on_tick=lease_callback("attempt", attempt_id, token),
            )
            if runner.version != saved["terraform"]:
                raise ProvisioningError("执行器版本已变化，请重新生成计划")
            runner.initialize()
            if not lease_callback("attempt", attempt_id, token)():
                raise ProvisioningError("执行租约已失效")
            # Initialization may take minutes; do not apply with cached authorization.
            attempt.actor.refresh_from_db()
            record = ProvisioningRequest.objects.select_related(
                "credential__source", "version__template"
            ).get(pk=record.pk)
            attempt.actor = authorize(attempt.actor, "execute", record.pk)
            check_credential_access(attempt.actor, record)
            with transaction.atomic():
                latest_plan = current_plan(record, attempt.plan_id, attempt.plan.digest)
                check_approval(record, latest_plan)
            if not getattr(settings, "PROVISIONING_ENABLED", False):
                raise ProvisioningError("资源创建功能已关闭")
            validate_resolved_resources(record, attempt.actor)
            attempt.actor = authorize(attempt.actor, "execute", record.pk)
            check_credential_access(attempt.actor, record)
            if not ProvisioningAttempt.objects.filter(
                pk=attempt_id,
                status="running",
                execution_token=token,
                lease_expires_at__gt=timezone.now(),
            ).update(apply_started_at=timezone.now()):
                raise ProvisioningError("执行租约已失效，禁止发起资源写入")
            applied = True
            try:
                runner.apply()
            finally:
                # Persist even a partial state. Never replace the confirmed plan artifact.
                try:
                    files = archive_workspace(workspace)
                    recovery_key = store.put({"files": files})
                    ProvisioningAttempt.objects.filter(
                        pk=attempt_id, status="running", execution_token=token
                    ).update(recovery_artifact_key=recovery_key)
                except Exception:
                    # Protection failure does not change a known cloud apply result.
                    pass
                try:
                    version = capture_state(
                        attempt_id, archive_workspace(workspace), execution_token=token
                    )
                    persisted = version.protection_status == "protected"
                except Exception:
                    # Keep the raw recovery copy and workspace; report protection separately.
                    persisted = False
        finally:
            # If encryption/storage fails, retain the private workspace for recovery.
            if (
                persisted
                and workspace.resolve().parent == store.working_root.resolve()
                and not workspace.is_symlink()
            ):
                try:
                    shutil.rmtree(workspace)
                except OSError:
                    # A private temporary directory can be cleaned by an operator later.
                    pass
        with transaction.atomic():
            ProvisioningRequest.objects.select_for_update().get(pk=record.pk)
            updated = ProvisioningAttempt.objects.filter(
                pk=attempt_id, status="running", execution_token=token
            ).update(status="applied", finished_at=timezone.now())
            if not updated:
                raise ProvisioningError("执行租约失效，云侧结果需核实")
            ProvisioningRequest.objects.filter(pk=record.pk).update(
                execution_status="success", inventory_status="pending"
            )
        event(record, attempt.actor, "created", "云资源创建成功，等待回读纳管", attempt.plan)
        from .notifications import notify

        notify(record, "created", attempt.plan_id, "资源创建成功，正在回读纳管")
        from .reconciliation import queue_reconciliation

        try:
            queue_reconciliation(attempt_id)
        except ProvisioningError:
            notify(
                record, "inventory_failed", attempt.plan_id, "资源已创建，但回读任务投递失败，请重新核实与纳管"
            )
    except Exception as exc:
        state = "needs_reconciliation" if applied else "failed"
        message = (
            str(exc) if isinstance(exc, ProvisioningError) else "资源交付异常，请核实执行环境与云资源实际结果"
        )
        with transaction.atomic():
            ProvisioningRequest.objects.select_for_update().get(
                pk=attempt.plan.request_id
            )
            if not ProvisioningAttempt.objects.filter(
                pk=attempt_id, status="running", execution_token=token
            ).update(status=state, error_message=message, finished_at=timezone.now()):
                return
            ProvisioningRequest.objects.filter(pk=attempt.plan.request_id).update(
                execution_status=state
            )
        event(attempt.plan.request, attempt.actor, state, message, attempt.plan)
        from .notifications import notify

        notify(attempt.plan.request, state, attempt.plan_id, message)


@shared_task(name="provisioning.recover_stale")
def recover_stale():
    cutoff = timezone.now() - timedelta(minutes=45)
    ProvisioningPlan.objects.filter(
        status__in=["queued", "running"], updated_at__lt=cutoff
    ).update(status="failed", error_message="计划生成超时或 Worker 中断，请重新生成")
    for attempt in ProvisioningAttempt.objects.filter(
        Q(status="queued", created_at__lt=cutoff)
        | Q(status="running", started_at__lt=cutoff)
    ).select_related("plan__request")[:100]:
        old_status = attempt.status
        status = "needs_reconciliation" if old_status == "running" else "failed"
        if not ProvisioningAttempt.objects.filter(
            pk=attempt.pk, status=old_status
        ).update(status=status, error_message="执行队列超时或 Worker 中断，已禁止自动重新创建，请核实云资源结果"):
            continue
        ProvisioningRequest.objects.filter(pk=attempt.plan.request_id).update(
            execution_status=status
        )
        if old_status == "running" and not attempt.recovery_artifact_key:
            try:
                store = ArtifactStore()
                folders = list(store.working_root.glob(f"attempt-{attempt.pk}-*"))
                if len(folders) == 1 and not folders[0].is_symlink():
                    key = store.put({"files": archive_workspace(folders[0])})
                    ProvisioningAttempt.objects.filter(pk=attempt.pk).update(
                        recovery_artifact_key=key
                    )
            except Exception:
                # Keep the uncertain outcome, never re-run apply to recover a missing state.
                pass
        from .notifications import notify

        notify(attempt.plan.request, status, attempt.plan_id, "执行进程中断，请核实云资源结果")
