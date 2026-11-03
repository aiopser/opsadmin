"""Resolve the actual frontend calls against deployment URLs and seeded API grants."""
import json
from pathlib import Path
import re

import pytest
from django.urls import resolve

from apps.permission.seeds.permissions import SYSTEM_PERMISSIONS


CONTRACTS = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "docs/integrations/observability-api-contracts.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "contract",
    CONTRACTS,
    ids=lambda row: f"{row['service']}-{row['name']}-{row['method']}",
)
def test_frontend_call_resolves_to_supported_backend_method_and_permission(contract):
    method, url = contract["method"].lower(), contract["url"]
    match = resolve(url)
    view = match.func
    assert method in view.cls.http_method_names
    if hasattr(view, "actions"):
        assert method in view.actions
        assert hasattr(view.cls, view.actions[method])
    else:
        assert hasattr(view.cls, method)
    assert any(
        re.fullmatch(permission.get("method") or "", method.upper())
        and re.fullmatch(
            re.escape(permission.get("path") or "").replace(":id", r"[^/]+"), url
        )
        for permission in SYSTEM_PERMISSIONS
    ), f"No seeded API permission: {method.upper()} {url}"


LIST_CALLS = {
    "getConsulConnections": "array",
    "getMonitoringTargets": "page",
    "getMonitoringRecords": "page",
    "getEnrollmentPolicies": "page",
    "getEnrollmentRuns": "page",
    "fetchJumpServers": "array",
    "getSecuritySubscriptions": "array",
    "getSecurityAdvisories": "page",
    "getSecurityCollections": "page",
    "getConsulTemplates": "array",
}


@pytest.fixture
def wire_actor(db, django_user_model):
    from apps.consul.models import ConsulConnection, ConsulTemplateFile
    from apps.cmdb.models import AssetHost
    from apps.monitoring.models import (
        MonitoringTarget,
        SyncRecord,
        EnrollmentPolicy,
        EnrollmentRun,
    )
    from apps.integrations.models import JumpServerConnection
    from apps.security.models import (
        SecuritySubscription,
        SecurityAdvisory,
        SecurityCollection,
    )
    from apps.automation.models import NotificationChannel, NotificationTemplate

    actor = django_user_model.objects.create_user(
        username="api-contract", is_superuser=True, job_status=True
    )
    connection = ConsulConnection.objects.create(
        pk=7, name="example", endpoint="https://consul.example.invalid"
    )
    file_host = AssetHost.objects.create(
        hostname="example",
        internal_ip="192.168.1.77",
        os_family="linux",
        connection_type="ssh",
    )
    ConsulTemplateFile.objects.create(
        name="example", host=file_host, path="/etc/consul-template/config/app.hcl"
    )
    target = MonitoringTarget.objects.create(
        pk=7, connection=connection, name="example", address="192.168.1.1"
    )
    SyncRecord.objects.create(
        target=target, target_name="example", actor=actor, operation="register"
    )
    policy = EnrollmentPolicy.objects.create(
        pk=7,
        name="example",
        connection=connection,
        scope="rule",
        match_rule={"os_family": "linux"},
    )
    EnrollmentRun.objects.create(
        policy=policy, policy_name="example", actor=actor, plan_digest="synthetic"
    )
    JumpServerConnection.objects.create(
        name="example",
        endpoint="https://jms.example.invalid",
        key_id="synthetic",
        node_id="00000000-0000-0000-0000-000000000001",
        secret_encrypted="synthetic",
    )
    sub = SecuritySubscription.objects.create(name="example", actor=actor)
    SecurityCollection.objects.create(subscription=sub, actor=actor)
    SecurityAdvisory.objects.create(
        stable_id="AVD-EXAMPLE",
        title="example",
        url="https://avd.aliyun.com/",
        category="example",
        published="2026-10-28",
        severity="unknown",
        fingerprint="example",
    )
    channel = NotificationChannel.objects.create(name="example", channel_type="webhook")
    NotificationTemplate.objects.create(
        name="example", code="example", channel=channel, body_template="{{ title }}"
    )
    return actor


@pytest.mark.django_db
@pytest.mark.parametrize(
    "contract",
    [row for row in CONTRACTS if row["name"] in LIST_CALLS],
    ids=lambda row: row["name"],
)
def test_frontend_list_envelope_matches_actual_api_response(contract, wire_actor):
    from rest_framework.test import APIRequestFactory, force_authenticate

    params = {**contract.get("params", {})}
    if LIST_CALLS[contract["name"]] == "page":
        params.update(pageNum=1, pageSize=20)
    request = APIRequestFactory().get(contract["url"], params)
    force_authenticate(request, user=wire_actor)
    response = resolve(contract["url"]).func(request)
    assert response.status_code == 200, response.data
    assert set(response.data) >= {"code", "data", "msg"}
    data = response.data["data"]
    if LIST_CALLS[contract["name"]] == "page":
        assert set(data) >= {"list", "total", "page", "size"}
        assert isinstance(data["list"], list)
        assert data["size"] == 20
        records = data["list"]
    else:
        assert isinstance(data, list)
        records = data
    assert records
    for row in records:
        assert isinstance(row["id"], int)
        assert not {
            "secret",
            "secret_encrypted",
            "token",
            "token_encrypted",
            "credentials_encrypted",
        }.intersection(row)
    if contract["name"] == "fetchJumpServers":
        assert records[0]["has_secret"] is True
    if contract["name"] == "getConsulTemplates":
        assert len(records[0]["revision"]) == 64
        assert records[0]["last_deploy_run"] is None

