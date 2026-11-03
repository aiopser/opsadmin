from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.cloud import collect_cloud_assets
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetSource
from apps.cmdb.serializers import AssetSourceSerializer
from apps.cmdb.sync_preview import cloud_asset_digest
from apps.cmdb.views import AssetSourceViewSet
from apps.cmdb.tasks import collect_cloud_import_preview


def test_cloud_asset_digest_ignores_provider_result_order():
    assets = [
        {"source_id": "i-1", "hostname": "web"},
        {"source_id": "i-2", "hostname": "db"},
    ]
    assert cloud_asset_digest(assets) == cloud_asset_digest(list(reversed(assets)))
    assert cloud_asset_digest(assets) != cloud_asset_digest([{**assets[0], "hostname": "changed"}, assets[1]])


@pytest.mark.django_db
def test_cloud_credentials_are_encrypted_and_never_serialized():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        serializer = AssetSourceSerializer(data={
            "code": "aliyun-test", "name": "Aliyun", "source_type": "cloud",
            "cloud_provider": "aliyun", "regions": ["cn-hangzhou"],
            "access_key_id": "test-id", "access_key_secret": "test-secret",
        })
        assert serializer.is_valid(), serializer.errors
        source = serializer.save()
        assert source.credentials_encrypted
        assert "test-secret" not in source.credentials_encrypted
        rendered = str(AssetSourceSerializer(source).data)
        assert "test-id" not in rendered
        assert "test-secret" not in rendered
        assert source.credentials_encrypted not in rendered
        assert AssetSourceSerializer(source).data["has_credentials"] is True


@pytest.mark.django_db
def test_cloud_collection_is_bounded_and_uses_only_configured_regions():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        source = AssetSource.objects.create(
            code="cloud-test", name="Cloud", source_type="cloud", cloud_provider="aliyun",
            regions=["cn-hangzhou", "cn-shanghai"],
            credentials_encrypted=encrypt_secret('{"access_key_id":"id","access_key_secret":"secret"}'),
        )
        with patch("apps.cmdb.cloud._aliyun_region", side_effect=lambda region, credentials: iter([{
            "source_id": region, "hostname": region, "internal_ip": "10.0.0.1"
        }])) as collect:
            result = collect_cloud_assets(source)
        assert [item["source_id"] for item in result] == source.regions
        assert collect.call_count == 2


def test_aliyun_pagination_maps_private_addresses_without_network():
    from apps.cmdb.cloud import _aliyun_region

    item = SimpleNamespace(
        instance_id="i-test", instance_name="web", host_name="web-host",
        vpc_attributes=SimpleNamespace(private_ip_address=SimpleNamespace(ip_address=["10.0.0.1"])),
        inner_ip_address=None, public_ip_address=SimpleNamespace(ip_address=["203.0.113.1"]),
        osname="Linux", ostype="linux", instance_type="ecs.t6",
        cpu=4, memory=8192, zone_id="cn-hangzhou-a",
    )
    response = SimpleNamespace(body=SimpleNamespace(
        instances=SimpleNamespace(instance=[item]), next_token=None,
    ))
    with patch("alibabacloud_ecs20140526.client.Client") as client:
        client.return_value.describe_instances.return_value = response
        client.return_value.describe_disks.return_value = SimpleNamespace(body=SimpleNamespace(
            disks=SimpleNamespace(disk=[
                SimpleNamespace(instance_id="i-test", disk_id="d-system", type="system", size=40),
                SimpleNamespace(instance_id="i-test", disk_id="d-data", type="data", size=100),
                SimpleNamespace(instance_id="i-test", disk_id="d-data2", type="data", size=200),
            ]), next_token=None,
        ))
        assets = list(_aliyun_region("cn-hangzhou", {"access_key_id": "id", "access_key_secret": "secret"}))
    assert assets[0]["internal_ip"] == "10.0.0.1"
    assert assets[0]["source_id"] == "i-test"
    assert assets[0]["asset_type"] == "cloud_instance"
    assert assets[0]["cpu_cores"] == 4
    assert assets[0]["memory_mb"] == 8192
    assert assets[0]["system_disk_gb"] == 40
    assert assets[0]["data_disk_gb"] == 300
    assert assets[0]["region"] == "cn-hangzhou"


def test_tencent_pagination_maps_private_addresses_without_network():
    from apps.cmdb.cloud import _tencent_region

    item = SimpleNamespace(
        InstanceId="ins-test", InstanceName="web", PrivateIpAddresses=["10.0.0.2"],
        PublicIpAddresses=[], OsName="Windows", InstanceType="S5",
        CPU=8, Memory=16, Placement=SimpleNamespace(Zone="ap-guangzhou-1"),
        SystemDisk=SimpleNamespace(DiskId="disk-system", DiskSize=50),
        DataDisks=[SimpleNamespace(DiskId="disk-data", DiskSize=100)],
    )
    response = SimpleNamespace(InstanceSet=[item], TotalCount=1)
    with patch("tencentcloud.cvm.v20170312.cvm_client.CvmClient") as client:
        client.return_value.DescribeInstances.return_value = response
        assets = list(_tencent_region("ap-guangzhou", {"access_key_id": "id", "access_key_secret": "secret"}))
    assert assets[0]["source_id"] == "ins-test"
    assert assets[0]["asset_type"] == "cloud_instance"
    assert assets[0]["os_family"] == "windows"
    assert assets[0]["cpu_cores"] == 8
    assert assets[0]["memory_mb"] == 16384
    assert assets[0]["system_disk_gb"] == 50
    assert assets[0]["data_disk_gb"] == 100
    assert assets[0]["region"] == "ap-guangzhou"


def test_aliyun_disks_paginates_and_sums_all_data_disks():
    from apps.cmdb.cloud import _aliyun_disks, _disk_specs
    from unittest.mock import Mock

    client = Mock()
    client.describe_disks.side_effect = [SimpleNamespace(body=SimpleNamespace(
        disks=SimpleNamespace(disk=[SimpleNamespace(instance_id="i-test", disk_id="d1", type="system", size=40)]), next_token="page2",
    )), SimpleNamespace(body=SimpleNamespace(
        disks=SimpleNamespace(disk=[SimpleNamespace(instance_id="i-test", disk_id="d2", type="data", size=100)]), next_token=None,
    ))]
    disks = _aliyun_disks(client, "cn-shanghai", {})
    assert _disk_specs(disks["i-test"])["data_disk_gb"] == 100
    assert client.describe_disks.call_args.args[0].next_token == "page2"


def test_aliyun_disk_permissions_fail_explicitly_without_leaking_credentials():
    from apps.cmdb.cloud import _aliyun_disks, CloudCollectionError
    from Tea.exceptions import TeaException
    from unittest.mock import Mock

    client = Mock()
    client.describe_disks.side_effect = TeaException({"code": "Forbidden.RAM", "message": "test-secret"})
    with pytest.raises(CloudCollectionError) as error:
        _aliyun_disks(client, "cn-shanghai", {"access_key_secret": "test-secret"})
    assert "ecs:DescribeDisks" in str(error.value)
    assert "Forbidden.RAM" in str(error.value)
    assert "test-secret" not in str(error.value)


def test_tencent_missing_specs_do_not_become_zero_updates():
    from apps.cmdb.cloud import _tencent_region

    item = SimpleNamespace(
        InstanceId="ins-test", InstanceName="web", PrivateIpAddresses=["10.0.0.2"],
        PublicIpAddresses=[], OsName="Linux", InstanceType="S5", CPU=None, Memory=None,
        SystemDisk=None, DataDisks=None,
    )
    with patch("tencentcloud.cvm.v20170312.cvm_client.CvmClient") as client:
        client.return_value.DescribeInstances.return_value = SimpleNamespace(InstanceSet=[item], TotalCount=1)
        assets = list(_tencent_region("ap-shanghai", {"access_key_id": "id", "access_key_secret": "secret"}))
    assert not {"cpu_cores", "memory_mb", "system_disk_gb", "data_disk_gb"}.intersection(assets[0])


@pytest.mark.django_db
def test_cloud_preview_must_match_confirmed_inventory():
    source = AssetSource.objects.create(
        code="cloud-preview", name="Cloud", source_type="cloud",
        cloud_provider="aliyun", regions=["cn-hangzhou"],
    )
    user = get_user_model().objects.create_superuser(
        username="cloud-admin", password="test-password", email="admin@example.com",
    )
    factory = APIRequestFactory()

    def call(action, path, payload):
        request = factory.post(path, payload, format="json")
        force_authenticate(request, user=user)
        return AssetSourceViewSet.as_view({"post": action})(request, pk=source.pk)

    assets = [{"source_id": "i-1", "hostname": "web", "internal_ip": "10.0.0.1"}]
    with patch("apps.cmdb.cloud.collect_cloud_assets", return_value=assets), patch(
        "apps.cmdb.views.collect_cloud_import_preview.apply_async",
        side_effect=lambda args, **kwargs: collect_cloud_import_preview(*args),
    ):
        preview = call("preview_cloud", "preview-cloud", {})
    assert preview.status_code == 200
    request = factory.get("preview-cloud-status", {"previewId": preview.data["data"]["previewId"]})
    force_authenticate(request, user=user)
    preview = AssetSourceViewSet.as_view({"get": "preview_cloud_status"})(request, pk=source.pk)
    token = preview.data["data"]["confirmationToken"]
    mismatch = call("sync_cloud", "sync-cloud", {"confirmationToken": token})
    assert mismatch.status_code == 400

    with patch("apps.cmdb.cloud.collect_cloud_assets", side_effect=AssertionError("unexpected recollect")), patch(
        "apps.cmdb.views.sync_asset_source.apply_async",
        return_value=SimpleNamespace(id="fake-task"),
    ):
        accepted = call("sync_cloud", "sync-cloud", {
            "confirmationToken": token, "selectedSourceIds": ["i-1"],
        })
    assert accepted.status_code == 200
    assert accepted.data["data"]["total_count"] == 1


@pytest.mark.django_db
def test_cloud_preview_status_is_private_and_exposes_collection_failure():
    source = AssetSource.objects.create(
        code="cloud-private-preview", name="Cloud", source_type="cloud",
        cloud_provider="aliyun", regions=["cn-hangzhou"],
    )
    owner = get_user_model().objects.create_superuser(
        username="preview-owner", password="test-password", email="owner@example.com",
    )
    other = get_user_model().objects.create_superuser(
        username="preview-other", password="test-password", email="other@example.com",
    )
    factory = APIRequestFactory()
    with patch("apps.cmdb.views.collect_cloud_import_preview.apply_async"):
        request = factory.post("/preview-cloud", {}, format="json")
        force_authenticate(request, user=owner)
        queued = AssetSourceViewSet.as_view({"post": "preview_cloud"})(request, pk=source.pk)
    preview_id = queued.data["data"]["previewId"]
    request = factory.get("/preview-cloud-status", {"previewId": preview_id})
    force_authenticate(request, user=other)
    hidden = AssetSourceViewSet.as_view({"get": "preview_cloud_status"})(request, pk=source.pk)
    assert hidden.status_code == 400

    with patch("apps.cmdb.cloud.collect_cloud_assets", side_effect=ValueError("secret credential text")):
        collect_cloud_import_preview(preview_id)
    request = factory.get("/preview-cloud-status", {"previewId": preview_id})
    force_authenticate(request, user=owner)
    failed = AssetSourceViewSet.as_view({"get": "preview_cloud_status"})(request, pk=source.pk)
    assert failed.status_code == 400
    assert "secret credential text" not in str(failed.data)


@pytest.mark.django_db
def test_cloud_sync_only_queues_selected_instances():
    source = AssetSource.objects.create(
        code="cloud-select", name="Cloud", source_type="cloud",
        cloud_provider="aliyun", regions=["cn-hangzhou"],
    )
    user = get_user_model().objects.create_superuser(
        username="cloud-select-admin", password="test-password", email="admin@example.com",
    )
    factory = APIRequestFactory()

    def call(action, payload):
        request = factory.post("/api/v1/cmdb/asset-sources/1/", payload, format="json")
        force_authenticate(request, user=user)
        return AssetSourceViewSet.as_view({"post": action})(request, pk=source.pk)

    assets = [
        {"source_id": "i-1", "hostname": "web", "internal_ip": "10.0.0.1"},
        {"source_id": "i-2", "hostname": "db", "internal_ip": "10.0.0.2"},
        {"source_id": "i-bad", "hostname": "no-ip", "internal_ip": ""},
    ]
    with patch("apps.cmdb.cloud.collect_cloud_assets", return_value=assets), patch(
        "apps.cmdb.views.collect_cloud_import_preview.apply_async",
        side_effect=lambda args, **kwargs: collect_cloud_import_preview(*args),
    ):
        preview = call("preview_cloud", {})
    request = factory.get("preview-cloud-status", {"previewId": preview.data["data"]["previewId"]})
    force_authenticate(request, user=user)
    preview = AssetSourceViewSet.as_view({"get": "preview_cloud_status"})(request, pk=source.pk)
    token = preview.data["data"]["confirmationToken"]

    with patch("apps.cmdb.cloud.collect_cloud_assets", side_effect=AssertionError("unexpected recollect")), patch(
        "apps.cmdb.views.sync_asset_source.apply_async",
        return_value=SimpleNamespace(id="fake-task"),
    ):
        rejected = call("sync_cloud", {
            "confirmationToken": token, "selectedSourceIds": ["i-3"],
        })
        assert rejected.data["code"] != 200
        duplicate = call("sync_cloud", {
            "confirmationToken": token, "selectedSourceIds": ["i-1", "i-1"],
        })
        assert duplicate.data["code"] != 200
        invalid = call("sync_cloud", {
            "confirmationToken": token, "selectedSourceIds": ["i-bad"],
        })
        assert invalid.data["code"] != 200
        accepted = call("sync_cloud", {
            "confirmationToken": token, "selectedSourceIds": ["i-2"],
        })
    assert accepted.status_code == 200
    record_id = accepted.data["data"]["id"]
    from apps.cmdb.models import AssetSyncRecord
    assert AssetSyncRecord.objects.get(pk=record_id).payload == [assets[1]]


@pytest.mark.django_db
def test_asset_sources_can_exclude_cloud_accounts_for_other_sources_tab():
    AssetSource.objects.create(code="cloud-only", name="Cloud", source_type="cloud")
    AssetSource.objects.create(code="external-only", name="External", source_type="external_cmdb")
    user = get_user_model().objects.create_superuser(
        username="source-filter-admin", password="test-password", email="admin@example.com",
    )
    request = APIRequestFactory().get(
        "/api/v1/cmdb/asset-sources?exclude_source_type=cloud&current=1&size=10"
    )
    force_authenticate(request, user=user)
    response = AssetSourceViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert [row["code"] for row in response.data["data"]["list"]] == ["external-only"]
