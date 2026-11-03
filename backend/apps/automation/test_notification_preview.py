import pytest


def test_asset_sync_catalog_and_preview_match_failure_notification_contract():
    from apps.automation.notification_preview import (
        notification_catalog,
        preview_notification,
    )
    from apps.automation.serializers import NotificationPreviewSerializer

    serializer = NotificationPreviewSerializer(data={"scenario": "asset_sync"})
    assert serializer.is_valid(), serializer.errors
    catalog = notification_catalog("asset_sync")
    assert any(
        item["expression"] == "{{ sync.errorMessage }}" for item in catalog["variables"]
    )
    preview = preview_notification(
        scenario="asset_sync",
        subject="{{ title }}",
        body="{{ sync.sourceName }}：{{ sync.errorMessage }}",
        receivers="",
    )
    assert preview["valid"] and "示例云账号" in preview["body"]


def test_failure_catalog_and_preview_use_same_sample_values():
    from apps.automation.notification_preview import (
        notification_catalog,
        preview_notification,
    )

    catalog = notification_catalog("failure")
    assert any(
        item["expression"] == "{{ run.failureReason }}" for item in catalog["variables"]
    )
    result = preview_notification(
        scenario="failure",
        subject="{{ title }}",
        body="{{ run.name }}：{{ run.failedStep }}",
        receivers="",
        sample_context={"run": {"name": "部署验证"}},
    )
    assert result["valid"]
    assert result["subject"] == "通知模板测试"
    assert result["body"] == "部署验证：测试步骤"


def test_workflow_catalog_uses_declared_fields_and_hides_secret_values():
    from apps.automation.notification_preview import (
        notification_catalog,
        preview_notification,
    )

    graph = {
        "inputSchema": {
            "fields": [
                {"name": "service", "type": "string", "default": "real-service"},
                {"name": "token", "type": "secret", "default": "never-show-this"},
            ]
        },
        "nodes": [
            {
                "id": "deploy-step",
                "name": "部署",
                "type": "command",
                "outputSchema": [{"name": "version", "type": "string"}],
            }
        ],
    }
    catalog = notification_catalog("workflow", graph)
    expressions = [item["expression"] for item in catalog["variables"]]
    assert '{{ nodes["deploy-step"].outputs["version"] }}' in expressions
    assert "never-show-this" not in str(catalog)
    assert "real-environment" not in str(catalog)
    assert "token" not in catalog["sampleContext"]["inputs"]
    result = preview_notification(
        scenario="workflow",
        subject='{{ inputs["service"] }}',
        body='{{ nodes["deploy-step"].outputs["version"] }}',
        receivers="",
        graph=graph,
    )
    assert result["valid"]
    assert result["body"] == "示例值"


def test_preview_reports_missing_variable_at_its_field():
    from apps.automation.notification_preview import preview_notification

    result = preview_notification(
        scenario="workflow",
        subject="{{ missing_title }}",
        body="plain text",
        receivers="",
    )
    assert not result["valid"]
    assert "subjectTemplate" in result["errors"]
    assert "missing_title" in result["errors"]["subjectTemplate"]


def test_workflow_scenario_provides_title_like_failure_scenario():
    from apps.automation.notification_preview import (
        notification_catalog,
        preview_notification,
    )

    catalog = notification_catalog("workflow")
    assert any(item["expression"] == "{{ title }}" for item in catalog["variables"])
    result = preview_notification(
        scenario="workflow",
        subject="{{ title }}",
        body="{{ title }}",
        receivers="",
    )
    assert result["valid"]
    assert result["subject"] == "流程通知：通知模板测试"
    assert result["body"] == "流程通知：通知模板测试"


def test_scenario_and_sample_namespaces_are_validated():
    from apps.automation.notification_preview import (
        notification_catalog,
        notification_context,
    )

    with pytest.raises(ValueError):
        notification_catalog("unknown")
    with pytest.raises(ValueError, match="run"):
        notification_context("workflow", {"run": {"name": "invalid"}})


def test_preview_rejects_declared_secret_inputs():
    from apps.automation.notification_preview import notification_context

    with pytest.raises(ValueError, match="秘密参数"):
        notification_context(
            "workflow",
            {"inputs": {"token": "private"}},
            {
                "inputSchema": {"fields": [{"name": "token", "type": "secret"}]},
            },
        )


def test_catalog_includes_resource_output_extractors_and_complete_output_object():
    from apps.automation.notification_preview import notification_catalog

    catalog = notification_catalog(
        "workflow",
        {
            "nodes": [
                {
                    "id": "script_1",
                    "name": "发布脚本",
                    "type": "script",
                    "commandVersion": {
                        "output_extractors": [{"name": "release", "type": "string"}]
                    },
                }
            ],
        },
    )
    expressions = {item["expression"] for item in catalog["variables"]}
    assert '{{ nodes["script_1"].outputs["release"] }}' in expressions
    assert '{{ nodes["script_1"].outputs }}' in expressions


@pytest.mark.django_db
def test_preview_api_renders_unsaved_template_without_sending():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.automation.models import NotificationRecord
    from apps.automation.views import NotificationTemplateViewSet

    user = get_user_model().objects.create_superuser(
        username="preview-admin",
        password="test",
        phone="13800000671",
    )
    request = APIRequestFactory().post(
        "/preview",
        {
            "scenario": "failure",
            "subjectTemplate": "{{ title }}",
            "bodyTemplate": "{{ run.failureReason }}",
            "sampleContext": {},
        },
        format="json",
    )
    force_authenticate(request, user=user)
    response = NotificationTemplateViewSet.as_view({"post": "preview"})(request)
    assert response.status_code == 200
    assert response.data["data"]["valid"]
    assert NotificationRecord.objects.count() == 0


@pytest.mark.django_db
def test_variables_api_loads_selected_workflow_without_real_defaults():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.automation.models import WorkflowTemplate, WorkflowVersion
    from apps.automation.views import NotificationTemplateViewSet

    user = get_user_model().objects.create_superuser(
        username="catalog-admin", password="test", phone="13800000672"
    )
    template = WorkflowTemplate.objects.create(
        name="测试流程", code="preview", status="published"
    )
    version = WorkflowVersion.objects.create(
        workflow=template,
        version=1,
        status="published",
        input_schema={
            "fields": [
                {"name": "service", "type": "string", "default": "private-default"}
            ]
        },
    )
    request = APIRequestFactory().get(
        "/variables", {"scenario": "workflow", "workflowVersionId": version.pk}
    )
    force_authenticate(request, user=user)
    response = NotificationTemplateViewSet.as_view({"get": "variables"})(request)
    assert response.status_code == 200
    data = response.data["data"]
    assert data["sampleContext"]["inputs"] == {"service": "示例值"}
    assert data["workflowVersions"] == [
        {"id": version.pk, "workflowName": "测试流程", "version": 1}
    ]
    assert "private-default" not in str(data)


@pytest.mark.django_db
def test_test_send_uses_exact_preview_context_and_rejects_invalid_template(monkeypatch):
    import json
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.automation.models import NotificationChannel, NotificationTemplate
    from apps.automation.views import NotificationTemplateViewSet
    from apps.cmdb.crypto import encrypt_secret
    from apps.jobs.models import NodeRun, WorkerPool, WorkflowRun
    from apps.jobs.node_executors import execute_notification

    user = get_user_model().objects.create_superuser(
        username="test-send-admin", password="test", phone="13800000673"
    )
    WorkerPool.objects.create(
        code="preview", name="preview", queue_name="task", is_default=True
    )
    channel = NotificationChannel.objects.create(
        name="test",
        channel_type="dingtalk",
        secret_encrypted=encrypt_secret("https://example.test/test"),
    )
    template = NotificationTemplate.objects.create(
        name="test",
        code="test",
        channel=channel,
        subject_template="{{ title }}",
        body_template="{{ run.name }}",
    )
    factory = APIRequestFactory()
    view = NotificationTemplateViewSet.as_view({"post": "test_send"})
    request = factory.post(
        "/test-send",
        {"scenario": "failure", "sampleContext": {"run": {"name": "自定义模拟运行"}}},
        format="json",
    )
    force_authenticate(request, user=user)
    response = view(request, pk=template.pk)
    assert response.status_code == 200
    run = WorkflowRun.objects.get(pk=response.data["data"]["workflowRunId"])
    node = NodeRun.objects.create(workflow_run=run, node_key="trial")
    sent = []

    def mock_request(method, url, headers, body, timeout):
        sent.append(json.loads(body))
        return 200, {}, '{"errcode": 0}'

    monkeypatch.setattr("apps.jobs.node_executors._request", mock_request)
    execute_notification(node, {})
    assert sent[0]["text"]["content"] == "自定义模拟运行"

    template.subject_template = "{{ missing_variable }}"
    template.save(update_fields=["subject_template"])
    request = factory.post("/test-send", {"scenario": "failure"}, format="json")
    force_authenticate(request, user=user)
    response = view(request, pk=template.pk)
    assert response.status_code == 400
    assert "missing_variable" in response.data["msg"]
    assert WorkflowRun.objects.count() == 1
