"""Environment diagnostics never connect to cloud platforms or expose secrets."""

import os
from importlib import metadata
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.fixture
def health_client(db):
    admin = get_user_model().objects.create_superuser(username="health-admin")
    client = APIClient()
    client.force_authenticate(admin)
    with patch("redis.Redis.from_url") as redis_client, patch(
        "celery.current_app.control.inspect"
    ) as inspect:
        redis_client.return_value.ping.return_value = True
        redis_client.return_value.llen.return_value = 0
        inspect.return_value.ping.return_value = {"test-worker": {"ok": "pong"}}
        inspect.return_value.active_queues.return_value = {
            "test-worker": [{"name": "task"}]
        }
        yield client


def test_health_reports_sdk_presence_and_installed_version(health_client):
    def find_sdk(module):
        if module == "alibabacloud_ecs20140526":
            raise ModuleNotFoundError("SDK not installed")
        return object()

    def package_version(name):
        if name == "alibabacloud-ecs20140526":
            raise metadata.PackageNotFoundError(name)
        return "3.1.178"

    with patch("importlib.util.find_spec", side_effect=find_sdk), patch(
        "importlib.metadata.version", side_effect=package_version
    ):
        response = health_client.get("/api/v1/jobs/dashboard/health")
    assert response.status_code == 200, response.data
    sdks = {item["name"]: item for item in response.data["data"]["environment"]["sdks"]}
    assert sdks == {
        "alibabacloud-ecs20140526": {
            "name": "alibabacloud-ecs20140526",
            "available": False,
            "version": None,
        },
        "tencentcloud-sdk-python-cvm": {
            "name": "tencentcloud-sdk-python-cvm",
            "available": True,
            "version": "3.1.178",
        },
    }


@pytest.mark.parametrize(
    "key,configured,valid",
    [
        ("", False, False),
        ("not-a-fernet-key", True, False),
        (Fernet.generate_key().decode(), True, True),
    ],
)
def test_health_checks_encryption_key_without_returning_it(
    health_client, key, configured, valid
):
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=key):
        response = health_client.get("/api/v1/jobs/dashboard/health")
    assert response.status_code == 200, response.data
    environment = response.data["data"]["environment"]
    assert environment["credentialsEncryptionConfigured"] is configured
    assert environment["credentialsEncryptionValid"] is valid
    if key:
        assert key not in str(response.data)


@pytest.mark.parametrize(
    "release_env,expected",
    [
        (
            {"DEVOPS_RELEASE": "release-20261020", "COMMIT_SHA": "abcdef"},
            "release-20261020",
        ),
        ({"COMMIT_SHA": "abcdef"}, "abcdef"),
        ({"DEVOPS_RELEASE": "  ", "COMMIT_SHA": "abcdef"}, "abcdef"),
        ({}, "unknown"),
    ],
)
def test_health_identifies_api_release_without_inventing_worker_version(
    health_client, release_env, expected
):
    with patch.object(os, "environ", release_env):
        response = health_client.get("/api/v1/jobs/dashboard/health")
    assert response.status_code == 200, response.data
    payload = response.data["data"]
    assert payload["environment"]["apiVersion"] == expected
    assert payload["environment"]["workersVersionStatus"] == "not_reported"
    assert payload["workers"]["count"] == 1
    assert payload["redis"]["healthy"] is True


def test_health_hides_local_paths_when_dependency_discovery_fails(health_client):
    path_marker = "private-python-installation-marker"
    with patch("importlib.util.find_spec", side_effect=ValueError(path_marker)), patch(
        "importlib.metadata.version", side_effect=OSError(path_marker)
    ):
        response = health_client.get("/api/v1/jobs/dashboard/health")
    assert response.status_code == 200, response.data
    sdks = response.data["data"]["environment"]["sdks"]
    assert all(item["available"] is False and item["version"] is None for item in sdks)
    assert path_marker not in str(response.data)


@pytest.mark.parametrize(
    "worker_version,status",
    [("release-a", "matched"), ("release-b", "mismatch"), ("unknown", "not_reported")],
)
def test_worker_release_comparison_requires_reported_versions(worker_version, status):
    from common.runtime_health import runtime_environment

    with patch.dict(os.environ, {"DEVOPS_RELEASE": "release-a"}):
        result = runtime_environment(
            {"worker": {"version": worker_version}}, ["worker"]
        )
    assert result["workersVersionStatus"] == status


def test_worker_inspection_only_returns_deployment_version():
    from apps.jobs.worker_health import deployment_version

    with patch.dict(os.environ, {"DEVOPS_RELEASE": "release-worker"}):
        assert deployment_version(None) == {"version": "release-worker"}
