from types import SimpleNamespace

import pytest

from apps.automation.models import WorkflowTemplate, WorkflowVersion
from apps.jobs.input_secrets import REDACTED_VALUE, resolve_workflow_inputs
from apps.jobs.models import ScheduledJob, WorkerPool, WorkflowTaskTicket
from apps.jobs.serializers import ScheduledJobSerializer, WorkflowTaskTicketSerializer


@pytest.fixture
def secret_definitions(db, django_user_model):
    actor = django_user_model.objects.create_superuser(
        username="secret-review", password="secret-review-pass"
    )
    template = WorkflowTemplate.objects.create(
        code="secret-review", name="Secret review", status="published"
    )
    version = WorkflowVersion.objects.create(
        workflow=template,
        version=1,
        status="published",
        input_schema={
            "fields": [{"name": "token", "type": "secret", "required": True}]
        },
        graph_snapshot={
            "nodes": [{"id": "s", "type": "start"}, {"id": "e", "type": "end"}],
            "edges": [{"id": "se", "source": "s", "target": "e"}],
        },
    )
    pool = WorkerPool.objects.create(
        code="secret-review",
        name="Secret pool",
        queue_name="secret-review",
        is_default=True,
    )
    return actor, version, pool


@pytest.mark.parametrize("kind", ["ticket", "schedule"])
def test_definitions_encrypt_secrets_and_never_return_ciphertext(
    secret_definitions, kind
):
    actor, version, pool = secret_definitions
    model, serializer = (
        (WorkflowTaskTicket, WorkflowTaskTicketSerializer)
        if kind == "ticket"
        else (ScheduledJob, ScheduledJobSerializer)
    )
    obj = model.objects.create(
        name="Secret source",
        workflow_version=version,
        worker_pool=pool,
        created_by=actor,
        input_vars={"token": "review-only-secret"},
    )
    obj.refresh_from_db()
    assert obj.input_vars["token"] == REDACTED_VALUE
    assert "review-only-secret" not in obj.secret_input_vars_encrypted
    assert resolve_workflow_inputs(obj)["token"] == "review-only-secret"
    data = serializer(obj).data
    assert "review-only-secret" not in str(data)
    assert "secret_input_vars_encrypted" not in data
    key = "inputVars" if kind == "ticket" else "input_vars"
    edit = serializer(
        obj,
        data={key: {"token": REDACTED_VALUE}},
        partial=True,
        context={"request": SimpleNamespace(user=actor)},
    )
    assert edit.is_valid(), edit.errors
    edit.save()
    assert resolve_workflow_inputs(edit.instance)["token"] == "review-only-secret"


@pytest.mark.parametrize("kind", ["ticket", "schedule"])
def test_direct_secret_updates_and_clear_do_not_restore_old_ciphertext(
    secret_definitions, kind
):
    actor, version, pool = secret_definitions
    model = WorkflowTaskTicket if kind == "ticket" else ScheduledJob
    obj = model.objects.create(
        name="Updated secret",
        workflow_version=version,
        worker_pool=pool,
        created_by=actor,
        input_vars={"token": "old-secret"},
    )
    obj.input_vars = {"token": "new-secret"}
    obj.save(update_fields=["input_vars"])
    obj.refresh_from_db()
    assert resolve_workflow_inputs(obj)["token"] == "new-secret"
    obj.input_vars = {"token": ""}
    obj.save(update_fields=["input_vars"])
    obj.refresh_from_db()
    assert resolve_workflow_inputs(obj)["token"] == ""
    assert obj.secret_input_vars_encrypted == ""


def test_legacy_orphan_definition_migration_encrypts_unclassifiable_values(
    secret_definitions,
):
    from importlib import import_module
    from django.apps import apps

    actor, version, pool = secret_definitions
    obj = WorkflowTaskTicket.objects.create(
        name="Orphan",
        workflow_version=version,
        worker_pool=pool,
        created_by=actor,
        input_vars={"token": "old"},
    )
    WorkflowTaskTicket.objects.filter(pk=obj.pk).update(
        workflow_version=None,
        input_vars={"legacy": "legacy-confidential"},
        secret_input_vars_encrypted="",
    )
    migration = import_module("apps.jobs.migrations.0020_definition_secret_inputs")
    migration.protect_existing_definitions(apps, None)
    obj.refresh_from_db()
    assert obj.input_vars == {"legacy": REDACTED_VALUE}
    assert resolve_workflow_inputs(obj)["legacy"] == "legacy-confidential"
