"""Selectors stay in definitions; each new run resolves current membership."""

import pytest
from rest_framework.test import APIClient
from apps.automation.models import NotificationChannel, NotificationTemplate

from apps.cmdb.models import AssetHost, HostGroup, HostGroupMembership, HostTag, HostTagBinding
from apps.jobs.models import WorkerPool, WorkflowRun
from apps.jobs.test_execution_entrypoints import published_workflow_version
from apps.jobs.views import _execution_preview
from common.workflow.schema import validate_graph


@pytest.fixture
def selection_context(user, monkeypatch):
    user.is_superuser = True
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    pool = WorkerPool.objects.create(code="selector", name="selector", queue_name="test.selector", is_default=True)
    host = AssetHost.objects.create(hostname="selector-host", internal_ip="192.0.2.50", os_family="linux", connection_type="ssh")
    group = HostGroup.objects.create(name="selector-group")
    HostGroupMembership.objects.create(group=group, host=host)
    tag = HostTag.objects.create(key="app", value="selector")
    HostTagBinding.objects.create(tag=tag, host=host)
    monkeypatch.setattr("apps.jobs.views.enqueue_workflow_run", lambda run_id: None)
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    return client, pool, host, group, tag, published_workflow_version()


@pytest.mark.django_db
def test_task_ticket_group_selection_is_preserved_and_resolved_on_each_run(selection_context):
    client, pool, host, group, tag, version = selection_context
    response = client.post("/api/v1/tasks/tickets", {
        "name": "group ticket", "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "hostIds": [], "groupIds": [group.pk], "tagIds": [],
    }, format="json")
    assert response.status_code == 200, response.data
    ticket = response.data["data"]
    assert ticket["hostIds"] == []
    assert ticket["groupIds"] == [group.pk]
    first = client.post(f"/api/v1/tasks/tickets/{ticket['id']}/run", {}, format="json")
    assert first.status_code == 200, first.data
    first_run = WorkflowRun.objects.get(pk=first.data["data"]["id"])
    second_host = AssetHost.objects.create(hostname="selector-host-2", internal_ip="192.0.2.51", os_family="linux", connection_type="ssh")
    HostGroupMembership.objects.create(group=group, host=second_host)
    second = client.post(f"/api/v1/tasks/tickets/{ticket['id']}/run", {}, format="json")
    assert second.status_code == 200, second.data
    second_run = WorkflowRun.objects.get(pk=second.data["data"]["id"])
    assert {target["host_id"] for target in first_run.target_snapshot} == {host.pk}
    assert {target["host_id"] for target in second_run.target_snapshot} == {host.pk, second_host.pk}
    assert second_run.target_selector == {"hostIds": [], "groupIds": [group.pk], "tagIds": []}


@pytest.mark.django_db
def test_ticket_failure_alert_inherits_or_overrides_workflow(selection_context):
    client, pool, host, _, _, version = selection_context
    channel = NotificationChannel.objects.create(name="alert", channel_type="email")
    template = NotificationTemplate.objects.create(name="failed", code="failed", channel=channel)
    workflow = version.workflow
    workflow.failure_alert = {"templateId": template.pk, "receivers": "workflow@example.test"}
    workflow.save(update_fields=["failure_alert"])

    for label, override, expected in (
        ("inherit", None, workflow.failure_alert),
        ("off", {}, {}),
        ("custom", {"templateId": template.pk, "receivers": "ticket@example.test"},
         {"templateId": template.pk, "receivers": "ticket@example.test"}),
    ):
        response = client.post("/api/v1/tasks/tickets", {
            "name": label, "workflowVersionId": version.pk, "workerPoolId": pool.pk,
            "hostIds": [host.pk], "failureAlert": override,
        }, format="json")
        assert response.status_code == 200, response.data
        ticket_id = response.data["data"]["id"]
        executed = client.post(f"/api/v1/tasks/tickets/{ticket_id}/run", {}, format="json")
        assert executed.status_code == 200, executed.data
        run = WorkflowRun.objects.get(pk=executed.data["data"]["id"])
        assert {key: run.failure_alert[key] for key in expected} == expected
        if expected:
            assert run.failure_alert["templateSnapshot"]["channelId"] == channel.pk
        else:
            assert run.failure_alert == {}


@pytest.mark.django_db
def test_schedule_tag_selection_survives_toggle_and_manual_execution(selection_context):
    client, pool, host, group, tag, version = selection_context
    response = client.post("/api/v1/jobs/scheduled-jobs", {
        "name": "tag schedule", "workflow_version": version.pk, "worker_pool": pool.pk,
        "host_ids": [], "group_ids": [], "tag_ids": [tag.pk], "cron_expression": "0 * * * *",
    }, format="json")
    assert response.status_code == 200, response.data
    schedule = response.data["data"]
    assert schedule["host_ids"] == []
    updated = client.patch(f"/api/v1/jobs/scheduled-jobs/{schedule['id']}", {"enabled": False}, format="json")
    assert updated.status_code == 200, updated.data
    assert updated.data["data"]["tag_ids"] == [tag.pk]
    run_response = client.post(f"/api/v1/jobs/scheduled-jobs/{schedule['id']}/run-now", {}, format="json")
    assert run_response.status_code == 200, run_response.data
    run = WorkflowRun.objects.get(pk=run_response.data["data"]["id"])
    assert run.trigger_type == WorkflowRun.TriggerType.MANUAL
    assert run_response.data["data"]["scheduledJobId"] == schedule["id"]
    assert run_response.data["data"]["scheduledJobName"] == schedule["name"]
    assert [target["host_id"] for target in run.target_snapshot] == [host.pk]
    assert run.target_selector == {"hostIds": [], "groupIds": [], "tagIds": [tag.pk]}


@pytest.mark.django_db
def test_schedule_manual_preview_rejects_changed_targets(selection_context):
    client, pool, host, group, tag, version = selection_context
    created = client.post("/api/v1/jobs/scheduled-jobs", {
        "name": "preview schedule", "workflow_version": version.pk,
        "worker_pool": pool.pk, "group_ids": [group.pk],
        "cron_expression": "0 * * * *",
    }, format="json")
    assert created.status_code == 200, created.data
    schedule_id = created.data["data"]["id"]
    preview = client.get(f"/api/v1/jobs/scheduled-jobs/{schedule_id}/preview")
    assert preview.status_code == 200, preview.data
    assert [target["hostId"] for target in preview.data["data"]["targets"]] == [host.pk]
    second = AssetHost.objects.create(
        hostname="schedule-drift", internal_ip="192.0.2.55",
        os_family="linux", connection_type="ssh",
    )
    HostGroupMembership.objects.create(group=group, host=second)
    run = client.post(f"/api/v1/jobs/scheduled-jobs/{schedule_id}/run-now", {
        "expectedTargetIds": [host.pk],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_schedule_save_rejects_targets_changed_after_confirmation(selection_context):
    client, pool, host, group, tag, version = selection_context
    preview = client.post("/api/v1/tasks/runs/validate", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "groupIds": [group.pk],
    }, format="json")
    assert preview.status_code == 200, preview.data
    second = AssetHost.objects.create(
        hostname="schedule-new-host", internal_ip="192.0.2.88",
        os_family="linux", connection_type="ssh",
    )
    HostGroupMembership.objects.create(group=group, host=second)
    saved = client.post("/api/v1/jobs/scheduled-jobs", {
        "name": "confirmed schedule", "workflow_version": version.pk,
        "worker_pool": pool.pk, "group_ids": [group.pk],
        "cron_expression": "0 * * * *",
        "expectedTargetIds": [host.pk],
        "expectedTargetFingerprint": preview.data["data"]["targetFingerprint"],
    }, format="json")
    assert saved.status_code == 400, saved.data


@pytest.mark.django_db
def test_schedule_save_accepts_unchanged_targets_after_confirmation(selection_context):
    client, pool, host, group, tag, version = selection_context
    preview = client.post("/api/v1/tasks/runs/validate", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "groupIds": [group.pk],
    }, format="json")
    assert preview.status_code == 200, preview.data
    saved = client.post("/api/v1/jobs/scheduled-jobs", {
        "name": "confirmed schedule", "workflow_version": version.pk,
        "worker_pool": pool.pk, "group_ids": [group.pk],
        "cron_expression": "0 * * * *",
        "expectedTargetIds": [host.pk],
        "expectedTargetFingerprint": preview.data["data"]["targetFingerprint"],
    }, format="json")
    assert saved.status_code == 200, saved.data


@pytest.mark.django_db
def test_unknown_tag_is_rejected_instead_of_silently_ignored(selection_context):
    client, pool, host, group, tag, version = selection_context
    response = client.post("/api/v1/tasks/runs", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "hostIds": [host.pk], "tagIds": [tag.pk + 9999],
    }, format="json")
    assert response.status_code == 400
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_preview_lists_resolved_targets_without_creating_run(selection_context):
    client, pool, host, group, tag, version = selection_context
    response = client.post("/api/v1/tasks/runs/validate", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "groupIds": [group.pk],
    }, format="json")
    assert response.status_code == 200, response.data
    preview = response.data["data"]
    assert preview["targetCount"] == 1
    assert preview["targets"] == [{"hostId": host.pk, "hostname": host.hostname, "address": host.internal_ip}]
    assert preview["steps"][0]["targetScope"] == "all"
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_run_preview_masks_secret_inputs(selection_context):
    client, pool, host, group, tag, version = selection_context
    version.input_schema = [{"name": "password", "label": "密码", "type": "secret"}]
    preview = _execution_preview(
        version,
        [{"host_id": host.pk, "hostname": host.hostname, "address": host.internal_ip}],
        pool,
        input_vars={"password": "do-not-show", "unknownToken": "also-hidden"},
    )
    assert preview["parameters"] == [{"name": "密码", "value": "已填写（保密）"}]
    assert "do-not-show" not in str(preview)
    assert "also-hidden" not in str(preview)


@pytest.mark.django_db
def test_ticket_preview_re_resolves_group_without_creating_run(selection_context):
    client, pool, host, group, tag, version = selection_context
    created = client.post("/api/v1/tasks/tickets", {
        "name": "preview ticket", "workflowVersionId": version.pk,
        "workerPoolId": pool.pk, "groupIds": [group.pk],
    }, format="json")
    assert created.status_code == 200, created.data
    ticket_id = created.data["data"]["id"]
    second = AssetHost.objects.create(
        hostname="preview-host-2", internal_ip="192.0.2.52",
        os_family="linux", connection_type="ssh",
    )
    HostGroupMembership.objects.create(group=group, host=second)
    response = client.get(f"/api/v1/tasks/tickets/{ticket_id}/preview")
    assert response.status_code == 200, response.data
    assert {item["hostId"] for item in response.data["data"]["targets"]} == {host.pk, second.pk}
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_ticket_run_rejects_targets_changed_after_preview(selection_context):
    client, pool, host, group, tag, version = selection_context
    created = client.post("/api/v1/tasks/tickets", {
        "name": "drift ticket", "workflowVersionId": version.pk,
        "workerPoolId": pool.pk, "groupIds": [group.pk],
    }, format="json")
    ticket_id = created.data["data"]["id"]
    second = AssetHost.objects.create(
        hostname="drift-host", internal_ip="192.0.2.53",
        os_family="linux", connection_type="ssh",
    )
    HostGroupMembership.objects.create(group=group, host=second)
    response = client.post(f"/api/v1/tasks/tickets/{ticket_id}/run", {
        "expectedTargetIds": [host.pk],
    }, format="json")
    assert response.status_code == 400, response.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_ansible_workflow_cannot_run_without_targets(selection_context):
    client, pool, host, group, tag, version = selection_context
    response = client.post("/api/v1/tasks/runs", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
    }, format="json")
    assert response.status_code == 400, response.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_rejects_targets_changed_after_preview(selection_context):
    client, pool, host, group, tag, version = selection_context
    second = AssetHost.objects.create(
        hostname="direct-drift-host", internal_ip="192.0.2.54",
        os_family="linux", connection_type="ssh",
    )
    HostGroupMembership.objects.create(group=group, host=second)
    response = client.post("/api/v1/tasks/runs", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "groupIds": [group.pk], "expectedTargetIds": [host.pk],
    }, format="json")
    assert response.status_code == 400, response.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_rejects_connection_changed_after_preview(selection_context):
    client, pool, host, group, tag, version = selection_context
    preview = client.post("/api/v1/tasks/runs/validate", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "hostIds": [host.pk],
    }, format="json")
    assert preview.status_code == 200, preview.data
    host.internal_ip = "192.0.2.99"
    host.save(update_fields=["internal_ip", "updated_at"])
    run = client.post("/api/v1/tasks/runs", {
        "workflowVersionId": version.pk, "workerPoolId": pool.pk,
        "hostIds": [host.pk], "expectedTargetIds": [host.pk],
        "expectedTargetFingerprint": preview.data["data"]["targetFingerprint"],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_rejects_engine_settings_changed_after_preview(selection_context):
    from apps.jobs.settings_service import save_engine_settings

    client, pool, host, group, tag, version = selection_context
    payload = {"workflowVersionId": version.pk, "workerPoolId": pool.pk, "hostIds": [host.pk]}
    preview = client.post("/api/v1/tasks/runs/validate", payload, format="json")
    assert preview.status_code == 200, preview.data
    save_engine_settings({"forks": 13})
    run = client.post("/api/v1/tasks/runs", {
        **payload, "expectedConfirmationFingerprint": preview.data["data"]["confirmationFingerprint"],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_ticket_run_rejects_definition_changed_after_preview(selection_context):
    from apps.jobs.models import WorkflowTaskTicket

    client, pool, host, group, tag, version = selection_context
    created = client.post("/api/v1/tasks/tickets", {
        "name": "config drift", "workflowVersionId": version.pk,
        "workerPoolId": pool.pk, "hostIds": [host.pk],
    }, format="json")
    ticket_id = created.data["data"]["id"]
    preview = client.get(f"/api/v1/tasks/tickets/{ticket_id}/preview")
    assert preview.status_code == 200, preview.data
    WorkflowTaskTicket.objects.filter(pk=ticket_id).update(forks=7)
    run = client.post(f"/api/v1/tasks/tickets/{ticket_id}/run", {
        "expectedConfirmationFingerprint": preview.data["data"]["confirmationFingerprint"],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_accepts_unchanged_confirmation(selection_context):
    client, pool, host, group, tag, version = selection_context
    payload = {"workflowVersionId": version.pk, "workerPoolId": pool.pk, "hostIds": [host.pk]}
    preview = client.post("/api/v1/tasks/runs/validate", payload, format="json")
    assert preview.status_code == 200, preview.data
    run = client.post("/api/v1/tasks/runs", {
        **payload,
        "expectedTargetFingerprint": preview.data["data"]["targetFingerprint"],
        "expectedConfirmationFingerprint": preview.data["data"]["confirmationFingerprint"],
    }, format="json")
    assert run.status_code == 200, run.data
    assert WorkflowRun.objects.count() == 1


@pytest.mark.django_db
def test_schedule_run_rejects_definition_changed_after_preview(selection_context):
    from apps.jobs.models import ScheduledJob

    client, pool, host, group, tag, version = selection_context
    created = client.post("/api/v1/jobs/scheduled-jobs", {
        "name": "config schedule", "workflow_version": version.pk,
        "worker_pool": pool.pk, "host_ids": [host.pk], "cron_expression": "0 * * * *",
    }, format="json")
    schedule_id = created.data["data"]["id"]
    preview = client.get(f"/api/v1/jobs/scheduled-jobs/{schedule_id}/preview")
    assert preview.status_code == 200, preview.data
    ScheduledJob.objects.filter(pk=schedule_id).update(timeout_seconds=41)
    run = client.post(f"/api/v1/jobs/scheduled-jobs/{schedule_id}/run-now", {
        "expectedConfirmationFingerprint": preview.data["data"]["confirmationFingerprint"],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_direct_run_rejects_worker_pool_changed_after_preview(selection_context):
    client, pool, host, group, tag, version = selection_context
    payload = {"workflowVersionId": version.pk, "workerPoolId": pool.pk, "hostIds": [host.pk]}
    preview = client.post("/api/v1/tasks/runs/validate", payload, format="json")
    assert preview.status_code == 200, preview.data
    pool.queue_name = "changed-queue"
    pool.save(update_fields=["queue_name", "updated_at"])
    run = client.post("/api/v1/tasks/runs", {
        **payload, "expectedConfirmationFingerprint": preview.data["data"]["confirmationFingerprint"],
    }, format="json")
    assert run.status_code == 400, run.data
    assert not WorkflowRun.objects.exists()


def test_workflow_node_cannot_embed_a_second_target_selector():
    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "work", "type": "command", "timeoutSeconds": 60,
             "config": {"hostIds": [999]}},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "work"},
            {"id": "b", "source": "work", "target": "end"},
        ],
    }
    assert any("不能重新指定目标主机" in error for error in validate_graph(graph))
