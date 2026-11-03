"""Suspended responsible actors must not reach cloud write transports."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from .contracts import canonical_digest
from .models import ProvisioningApproval, ProvisioningAttempt
from .test_contract import ready_plan, request_record


@pytest.mark.parametrize("when", ["before_worker", "during_initialize"])
def test_suspended_responsible_actor_cannot_apply(
    request_record, settings, tmp_path, when
) -> None:
    from .tasks import apply_plan

    settings.PROVISIONING_ENABLED = True
    record = request_record
    record.approval_status = "approved"
    record.execution_status = "queued"
    record.save()
    plan = ready_plan(record)
    saved = {"files": {}, "terraform": "1.9.8"}
    plan.digest = canonical_digest(
        {
            "files": {},
            "inputs": plan.input_digest,
            "credential_revision": 1,
            "terraform": "1.9.8",
        }
    )
    saved["digest"] = plan.digest
    plan.confirmed_by = record.created_by
    plan.save()
    reviewer = get_user_model().objects.create_superuser(username="final-reviewer")
    ProvisioningApproval.objects.create(
        plan=plan, actor=reviewer, digest=plan.digest, decision="approved"
    )
    attempt = ProvisioningAttempt.objects.create(
        plan=plan, actor=record.created_by, idempotency_key="final-review-once"
    )
    working = tmp_path / "working"
    working.mkdir()

    def suspend() -> None:
        get_user_model().objects.filter(pk=record.created_by_id).update(
            job_status=False
        )

    if when == "before_worker":
        suspend()
    with patch("apps.provisioning.tasks.ArtifactStore") as store, patch(
        "apps.provisioning.tasks.TerraformRunner"
    ) as runner, patch(
        "apps.provisioning.tasks.credential_environment", return_value={}
    ), patch(
        "apps.provisioning.reconciliation.reconcile_attempt.apply_async"
    ):
        store.return_value.working_root = working
        store.return_value.get.return_value = saved
        store.return_value.put.return_value = "final-review-recovery"
        runner.return_value.version = "1.9.8"
        if when == "during_initialize":
            runner.return_value.initialize.side_effect = suspend
        apply_plan(attempt.pk)
        runner.return_value.apply.assert_not_called()


def test_suspended_plan_owner_cannot_prepare_cloud_plan(request_record) -> None:
    from .services import snapshot
    from .tasks import build_plan

    record = request_record
    plan = ready_plan(record)
    plan.status = "queued"
    plan.input_digest = canonical_digest(snapshot(record))
    plan.save()
    get_user_model().objects.filter(pk=record.created_by_id).update(job_status=False)
    with patch("apps.provisioning.tasks.TerraformRunner") as runner, patch(
        "apps.provisioning.catalog.validation.resolve_request_resources",
        return_value={},
    ) as catalog, patch("apps.provisioning.tasks.prepare_bundle"):
        build_plan(plan.pk)
        catalog.assert_not_called()
        runner.assert_not_called()
