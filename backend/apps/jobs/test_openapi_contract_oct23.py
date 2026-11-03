"""Schema assertions for the actual payload shapes at custom API endpoints."""

import pytest
from drf_spectacular.generators import SchemaGenerator
from rest_framework import serializers

from common.api.schema import api_envelope_serializer


@pytest.fixture(scope="module")
def schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def resolve(schema, value):
    while "$ref" in value:
        value = schema["components"]["schemas"][value["$ref"].rsplit("/", 1)[-1]]
    return value


def payload(schema, path, method="get"):
    response = schema["paths"][path][method]["responses"]["200"]
    assert "content" in response, f"{path} is missing its response contract"
    envelope = resolve(schema, response["content"]["application/json"]["schema"])
    assert envelope["properties"]["code"]["type"] == "string"
    assert "msg" in envelope["properties"]
    assert "message" not in envelope["properties"]
    return resolve(schema, envelope["properties"]["data"])


def test_envelope_matches_business_response_field_names_and_code_type():
    envelope = api_envelope_serializer("ProbeEnvelope", serializers.CharField())
    assert set(envelope.fields) == {"code", "data", "msg"}
    assert isinstance(envelope.fields["code"], serializers.CharField)


@pytest.mark.parametrize(
    "path,fields",
    [
        ("/api/v1/jobs/security/stats", {"ruleCount", "monthBlocked", "accidents"}),
        (
            "/api/v1/jobs/dashboard/stats",
            {
                "todayExecutions",
                "finishedExecutions",
                "successRate",
                "avgResponseSeconds",
                "scheduledExecutions",
                "blockedCommands",
            },
        ),
        (
            "/api/v1/jobs/dashboard/execution-distribution",
            {"periodDays", "total", "items"},
        ),
        (
            "/api/v1/jobs/dashboard/health",
            {
                "redis",
                "workers",
                "queues",
                "websocket",
                "sevenDay",
                "checkedAt",
                "environment",
            },
        ),
        (
            "/api/v1/jobs/settings/engine",
            {
                "timeout",
                "forks",
                "host_strategy",
                "serial_batch",
                "max_fail_percentage",
            },
        ),
        ("/api/v1/cmdb/search", {"hosts", "hostGroups", "assetSources"}),
        (
            "/api/v1/provisioning/catalog",
            {"items", "hasMore", "nextCursor", "observedAt", "warnings"},
        ),
        (
            "/api/v1/provisioning/catalog/configuration",
            {"items", "hasMore", "nextCursor", "observedAt", "warnings"},
        ),
        (
            "/api/v1/provisioning/operations/health",
            {
                "workers",
                "queued",
                "uncertain",
                "incidents",
                "observedAt",
                "storage",
                "retention",
            },
        ),
        (
            "/api/v1/configs/public",
            {"basic.system.name", "basic.login.title", "basic.user.default_avatar"},
        ),
        ("/api/v1/logs", {"list", "total", "count", "page", "size"}),
        (
            "/api/v1/logs/analytics/overview",
            {
                "todayUvCount",
                "totalUvCount",
                "uvGrowthRate",
                "todayPvCount",
                "totalPvCount",
                "pvGrowthRate",
            },
        ),
        ("/api/v1/logs/analytics/trend", {"dates", "pvList", "uvList"}),
    ],
)
def test_custom_endpoint_has_its_real_named_response_fields(schema, path, fields):
    assert set(payload(schema, path)["properties"]) == fields


def test_recent_dashboard_is_a_list_of_run_summaries(schema):
    data = payload(schema, "/api/v1/jobs/dashboard/recent")
    assert data["type"] == "array"
    assert set(resolve(schema, data["items"])["properties"]) == {
        "id",
        "name",
        "type",
        "target",
        "status",
        "executor",
        "time",
    }


def test_upload_uses_binary_multipart_and_returns_name_and_url(schema):
    operation = schema["paths"]["/api/v1/files"]["post"]
    assert "requestBody" in operation
    request = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert resolve(schema, request)["properties"]["file"]["format"] == "binary"
    assert set(payload(schema, "/api/v1/files", "post")["properties"]) == {
        "name",
        "url",
    }


def test_dynamic_catalog_item_preserves_named_fields_and_free_attributes(schema):
    data = payload(schema, "/api/v1/provisioning/catalog")
    item = resolve(schema, data["properties"]["items"]["items"])
    assert set(item["properties"]) == {
        "id",
        "name",
        "description",
        "available",
        "unavailableReason",
        "attributes",
    }
    assert item["properties"]["attributes"]["type"] == "object"


def test_engine_update_documents_the_optional_partial_settings(schema):
    operation = schema["paths"]["/api/v1/jobs/settings/engine"]["put"]
    assert "requestBody" in operation
    fields = resolve(
        schema, operation["requestBody"]["content"]["application/json"]["schema"]
    )
    assert fields["properties"]["timeout"]["type"] == "integer"
    assert not fields.get("required")


def test_probe_path_uses_an_integer_identity(schema):
    parameters = schema["paths"]["/api/v1/cmdb/credential-refs/probes/{probe_id}"][
        "get"
    ]["parameters"]
    probe_id = next(item for item in parameters if item["name"] == "probe_id")
    assert probe_id["schema"]["type"] == "integer"
