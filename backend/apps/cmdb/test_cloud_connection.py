from unittest.mock import patch
import json

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.cloud import probe_public_cloud
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetSource, AssetHost
from apps.cmdb.serializers import AssetSourceSerializer
from apps.cmdb.views import AssetSourceViewSet


def test_aliyun_permission_error_exposes_safe_diagnostics():
    from Tea.exceptions import TeaException

    error = TeaException(
        {
            "code": "Forbidden.RAM",
            "message": "Denied ecs:DescribeInstances test-secret https://example.com/?Signature=private-signature",
            "data": {"RequestId": "req-123", "statusCode": 403},
        }
    )
    with patch("alibabacloud_ecs20140526.client.Client", side_effect=error):
        result = probe_public_cloud(
            "aliyun",
            ["cn-shanghai"],
            {
                "access_key_id": "test-id",
                "access_key_secret": "test-secret",
            },
        )[0]
    assert result["category"] == "permission"
    assert result["errorCode"] == "Forbidden.RAM"
    assert result["requestId"] == "req-123"
    assert result["httpStatus"] == 403
    assert "ecs:DescribeInstances" in result["detail"]
    assert "test-secret" not in str(result)
    assert "private-signature" not in str(result)


def test_tencent_error_preserves_request_id_and_authentication_category():
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
        TencentCloudSDKException,
    )

    with patch(
        "tencentcloud.cvm.v20170312.cvm_client.CvmClient",
        side_effect=TencentCloudSDKException(
            "AuthFailure.SecretIdNotFound",
            "SecretId is invalid",
            "req-tencent",
        ),
    ):
        result = probe_public_cloud(
            "tencent",
            ["ap-shanghai"],
            {
                "access_key_id": "test-id",
                "access_key_secret": "test-secret",
            },
        )[0]
    assert result["category"] == "authentication"
    assert result["requestId"] == "req-tencent"


def test_timeout_and_missing_dependency_have_distinct_guidance():
    for error, category in (
        (TimeoutError("timed out"), "timeout"),
        (ModuleNotFoundError("missing sdk"), "dependency"),
    ):
        with patch(
            "tencentcloud.cvm.v20170312.cvm_client.CvmClient", side_effect=error
        ):
            result = probe_public_cloud(
                "tencent",
                ["ap-shanghai"],
                {
                    "access_key_id": "test-id",
                    "access_key_secret": "test-secret",
                },
            )[0]
        assert result["category"] == category
        assert result["suggestion"]


def test_authentication_403_is_not_misclassified_as_permission_failure():
    from Tea.exceptions import TeaException
    from apps.cmdb.cloud_diagnostics import cloud_probe_error

    result = cloud_probe_error(
        TeaException(
            {
                "code": "InvalidAccessKeyId.NotFound",
                "message": "Invalid access key",
                "data": {"statusCode": 403},
            }
        ),
        {"access_key_id": "test-id", "access_key_secret": "test-secret"},
    )
    assert result["category"] == "authentication"


def test_wrapped_network_errors_and_response_redaction():
    import socket
    from Tea.exceptions import UnretryableException
    from apps.cmdb.cloud_diagnostics import cloud_probe_error

    result = cloud_probe_error(
        UnretryableException(None, socket.gaierror("getaddrinfo failed")), {}
    )
    assert result["category"] == "dns"
    error = Exception(
        "Authorization: Bearer private-token\nSignature=private-signature\nrequest failed test-secret"
    )
    result = cloud_probe_error(error, {"access_key_secret": "test-secret"})
    assert not any(
        value in str(result)
        for value in ("private-token", "private-signature", "test-secret")
    )


def test_connection_queries_only_one_page_per_region():
    with patch("tencentcloud.cvm.v20170312.cvm_client.CvmClient") as client:
        result = probe_public_cloud(
            "tencent",
            ["ap-guangzhou"],
            {
                "access_key_id": "test-id",
                "access_key_secret": "test-secret",
            },
        )
    assert result[0]["region"] == "ap-guangzhou" and result[0]["success"] is True
    assert result[0]["checks"][0]["key"] == "instances"
    assert client.return_value.DescribeInstances.call_count == 1


def test_connection_does_not_expose_sdk_error_secrets():
    with patch(
        "tencentcloud.cvm.v20170312.cvm_client.CvmClient",
        side_effect=Exception("test-secret"),
    ):
        result = probe_public_cloud(
            "tencent",
            ["ap-guangzhou"],
            {
                "access_key_id": "test-id",
                "access_key_secret": "test-secret",
            },
        )
    assert result[0]["success"] is False
    assert "test-secret" not in str(result)


def test_aliyun_connection_is_a_bounded_read_only_query():
    with patch("alibabacloud_ecs20140526.client.Client") as client:
        result = probe_public_cloud(
            "aliyun",
            ["cn-hangzhou"],
            {
                "access_key_id": "test-id",
                "access_key_secret": "test-secret",
            },
        )
    assert result[0]["success"] is True
    assert client.return_value.describe_instances.call_count == 1
    config = client.call_args.args[0]
    assert config.connect_timeout == config.read_timeout == 3000
    assert client.return_value.describe_instances.call_args.args[0].page_size == 1


def test_aliyun_probe_reports_disk_permission_failure_separately():
    from Tea.exceptions import TeaException

    with patch("alibabacloud_ecs20140526.client.Client") as client:
        client.return_value.describe_disks.side_effect = TeaException(
            {
                "code": "Forbidden.RAM",
                "message": "disk denied",
                "data": {"RequestId": "disk-request"},
            }
        )
        result = probe_public_cloud(
            "aliyun",
            ["cn-shanghai"],
            {"access_key_id": "test-id", "access_key_secret": "test-secret"},
        )[0]
    assert result["success"] is False
    assert result["checks"][0]["success"] is True
    assert result["checks"][1]["key"] == "disks"
    assert result["checks"][1]["success"] is False
    assert result["requestId"] == "disk-request"


@pytest.mark.django_db
def test_cloud_probe_scope_is_bounded_and_cannot_test_unconfigured_regions():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        source = AssetSource.objects.create(
            code="probe-scope",
            name="Scope",
            source_type="cloud",
            cloud_provider="aliyun",
            regions=[f"cn-test-{index}" for index in range(8)],
            credentials_encrypted=encrypt_secret(
                json.dumps({"access_key_id": "id", "access_key_secret": "secret"})
            ),
        )
        user = get_user_model().objects.create_superuser(username="probe-scope")

        def call(payload):
            request = APIRequestFactory().post(
                "/api/v1/cmdb/asset-sources/test-cloud-connection",
                {"source_id": source.pk, **payload},
                format="json",
            )
            force_authenticate(request, user=user)
            return AssetSourceViewSet.as_view({"post": "test_cloud_connection"})(
                request
            )

        with patch("apps.cmdb.cloud.probe_public_cloud", return_value=[]) as probe:
            response = call({})
            assert response.status_code == 200
            assert len(probe.call_args.args[1]) == 5
            assert response.data["data"]["untestedRegions"] == source.regions[5:]
            response = call({"test_regions": source.regions[5:]})
            assert response.status_code == 200
            assert probe.call_args.args[1] == source.regions[5:]
            assert call({"test_regions": ["cn-unconfigured"]}).status_code == 400
            assert call({"test_regions": source.regions}).status_code == 400


@pytest.mark.django_db
def test_saved_credentials_can_be_tested_and_edit_keeps_secret():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        source = AssetSource.objects.create(
            code="probe",
            name="Probe",
            source_type="cloud",
            cloud_provider="tencent",
            regions=["ap-guangzhou"],
            credentials_encrypted=encrypt_secret(
                json.dumps(
                    {
                        "access_key_id": "long-test-key-id",
                        "access_key_secret": "test-secret",
                    }
                )
            ),
        )
        encrypted = source.credentials_encrypted
        rendered = AssetSourceSerializer(source).data
        assert rendered["masked_access_key_id"] == "****y-id"
        assert "test-secret" not in str(rendered)
        serializer = AssetSourceSerializer(
            source, data={"name": "Renamed"}, partial=True
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        user = get_user_model().objects.create_superuser(
            username="cloud-probe", password="test-password"
        )
        for override in (
            {},
            {"access_key_id": "new-id", "access_key_secret": "new-secret"},
        ):
            request = APIRequestFactory().post(
                "/api/v1/cmdb/asset-sources/test-cloud-connection",
                {
                    "source_id": source.pk,
                    **override,
                },
                format="json",
            )
            force_authenticate(request, user=user)
            with patch("apps.cmdb.cloud.probe_public_cloud", return_value=[]) as probe:
                response = AssetSourceViewSet.as_view(
                    {"post": "test_cloud_connection"}
                )(request)
            assert response.status_code == 200, response.data
            assert probe.call_args.args[2]["access_key_id"] == override.get(
                "access_key_id", "long-test-key-id"
            )
        source.refresh_from_db()
        assert source.credentials_encrypted == encrypted
        assert not AssetHost.objects.exists()
