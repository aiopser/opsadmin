"""OpenAPI contracts for automation APIViews with custom response payloads."""

from contextlib import redirect_stderr
from io import StringIO

import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.automation.urls import urlpatterns


TARGET_METHODS = {
    "v1/automation/templates": ("get",),
    "v1/automation/node-resources": ("get", "post"),
    "v1/notifications/email-settings": ("get", "put"),
    "v1/notifications/email-settings/test-connection": ("post",),
    "v1/notifications/email-settings/test": ("post",),
    "v1/notifications/history-settings": ("get", "put"),
    "v1/notifications/history-settings/purge": ("post",),
    "v1/notifications/wecom-settings": ("get", "put"),
    "v1/notifications/wecom-settings/test-connection": ("post",),
    "v1/notifications/dingtalk-settings": ("get", "put"),
    "v1/notifications/dingtalk-settings/test-connection": ("post",),
    "v1/notifications/feishu-settings": ("get", "put"),
    "v1/notifications/feishu-settings/test-connection": ("post",),
}


@pytest.fixture(scope="module")
def schema_generation() -> tuple[dict, str]:
    patterns = [
        pattern for pattern in urlpatterns if str(pattern.pattern) in TARGET_METHODS
    ]
    diagnostics = StringIO()
    with redirect_stderr(diagnostics):
        schema = SchemaGenerator(patterns=patterns).get_schema(
            request=None, public=True
        )
    return schema, diagnostics.getvalue()


@pytest.fixture(scope="module")
def schema(schema_generation: tuple[dict, str]) -> dict:
    return schema_generation[0]


def test_schema_has_no_missing_dtos_or_conflicting_components(
    schema_generation: tuple[dict, str],
) -> None:
    diagnostics = schema_generation[1]
    assert "Error [" not in diagnostics
    assert "Encountered 2 components" not in diagnostics


def resolve(schema: dict, value: dict) -> dict:
    while "$ref" in value:
        value = schema["components"]["schemas"][value["$ref"].rsplit("/", 1)[1]]
    return value


def response_data(schema: dict, path: str, method: str) -> dict:
    response = schema["paths"][f"/{path}"][method]["responses"]["200"]
    envelope = resolve(schema, response["content"]["application/json"]["schema"])
    assert set(envelope["properties"]) == {"code", "data", "msg"}
    assert envelope["properties"]["code"]["type"] == "string"
    assert envelope["properties"]["msg"]["nullable"] is True
    return resolve(schema, envelope["properties"]["data"])


def request_data(schema: dict, path: str, method: str) -> dict:
    request = schema["paths"][f"/{path}"][method]["requestBody"]
    return resolve(schema, request["content"]["application/json"]["schema"])


@pytest.mark.parametrize(
    ("path", "method"),
    [(path, method) for path, methods in TARGET_METHODS.items() for method in methods],
)
def test_custom_views_document_real_success_envelopes(
    schema: dict, path: str, method: str
) -> None:
    data = response_data(schema, path, method)
    assert "properties" in data or data.get("type") == "array"


def test_templates_document_command_and_workflow_variants(schema: dict) -> None:
    data = response_data(schema, "v1/automation/templates", "get")
    assert data["type"] == "array"
    item = resolve(schema, data["items"])
    variants = [resolve(schema, variant) for variant in item["oneOf"]]
    assert len(variants) == 2
    assert {
        "argumentSchema",
        "defaultVars",
        "outputExtractors",
        "timeoutSeconds",
    } <= set(variants[0]["properties"])
    assert {"inputSchema", "targetSelectorSchema"} <= set(variants[1]["properties"])


def test_node_catalog_documents_resource_variants_and_creation(schema: dict) -> None:
    path = "v1/automation/node-resources"
    data = response_data(schema, path, "get")
    assert set(data["properties"]) == {"types", "resources"}
    resource_type = resolve(schema, data["properties"]["types"]["items"])
    assert {
        "nodeType",
        "resourceType",
        "resourceCount",
        "createRoute",
        "createRouteQuery",
    } <= set(resource_type["properties"])
    resource = resolve(schema, data["properties"]["resources"]["items"])
    assert len(resource["oneOf"]) == 4
    create = request_data(schema, path, "post")
    assert {"resourceKind", "commandType"} <= set(create["required"])
    assert {"content", "moduleName", "parameterDocs"} <= set(create["properties"])
    assert not {"content", "moduleName"} & set(create["required"])
    assert create["properties"]["parameterDocs"]["type"] == "array"
    created = response_data(schema, path, "post")
    assert set(created["properties"]) == {"resource", "version"}


def test_email_settings_distinguish_saved_state_and_connection_input(
    schema: dict,
) -> None:
    path = "v1/notifications/email-settings"
    saved = response_data(schema, path, "get")
    assert {"hasPassword", "configured", "fromEmail", "titlePrefix"} <= set(
        saved["properties"]
    )
    assert "password" not in saved["properties"]
    update = request_data(schema, path, "put")
    assert update["properties"]["password"]["writeOnly"] is True
    assert {"name", "fromEmail", "host", "port", "timeout"} <= set(update["required"])
    connection = request_data(schema, f"{path}/test-connection", "post")
    assert set(connection["required"]) == {"host", "port", "timeout"}
    assert "fromEmail" not in connection["properties"]
    recipient = request_data(schema, f"{path}/test", "post")
    assert set(recipient["properties"]) == {"recipient"}


@pytest.mark.parametrize("provider", ("wecom", "dingtalk", "feishu"))
def test_app_settings_document_secret_and_provider_requirements(
    schema: dict, provider: str
) -> None:
    path = f"v1/notifications/{provider}-settings"
    saved = response_data(schema, path, "get")
    assert set(saved["properties"]) == {
        "provider",
        "appId",
        "agentId",
        "apiBase",
        "hasSecret",
        "configured",
    }
    update = request_data(schema, path, "put")
    assert update["properties"]["appSecret"]["writeOnly"] is True
    assert ("agentId" in update["required"]) is (provider == "wecom")
    connection = request_data(schema, f"{path}/test-connection", "post")
    assert "agentId" not in connection["properties"]
    assert connection["required"] == ["appId"]


def test_history_schema_documents_bounded_retention_and_purge_results(
    schema: dict,
) -> None:
    path = "v1/notifications/history-settings"
    update = request_data(schema, path, "put")
    retention = update["properties"]["retentionDays"]
    assert retention["minimum"] == 1
    assert retention["maximum"] == 3650
    purge = request_data(schema, f"{path}/purge", "post")
    assert set(purge["properties"]) == {"retentionDays", "dryRun"}
    result = response_data(schema, f"{path}/purge", "post")
    assert set(result["properties"]) == {"count", "deleted", "dryRun"}
