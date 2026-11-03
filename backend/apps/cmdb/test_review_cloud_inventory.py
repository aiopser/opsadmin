from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.cmdb.cloud import _aliyun_region
from apps.cmdb.models import AssetHost, AssetSource, AssetSyncRecord
from apps.cmdb.sync_preview import preview_asset_sync
from apps.cmdb.tasks import sync_asset_source


def test_aliyun_eip_is_preserved_as_external_address():
    item = SimpleNamespace(
        instance_id="i-eip",
        instance_name="eip",
        host_name="eip",
        vpc_attributes=None,
        inner_ip_address=SimpleNamespace(ip_address=["10.0.0.1"]),
        public_ip_address=SimpleNamespace(ip_address=[]),
        eip_address=SimpleNamespace(ip_address="203.0.113.51"),
        osname="Linux",
        ostype="linux",
        instance_type="ecs.test",
    )
    with patch("alibabacloud_ecs20140526.client.Client") as client:
        client.return_value.describe_instances.return_value = SimpleNamespace(
            body=SimpleNamespace(
                instances=SimpleNamespace(instance=[item]),
                next_token=None,
            )
        )
        client.return_value.describe_disks.return_value = SimpleNamespace(
            body=SimpleNamespace(disks=None, next_token=None)
        )
        assets = list(
            _aliyun_region(
                "cn-shanghai", {"access_key_id": "id", "access_key_secret": "secret"}
            )
        )
    assert assets[0]["external_ip"] == "203.0.113.51"


@pytest.mark.django_db
def test_windows_import_defaults_and_preserves_manual_connection_on_resync():
    source = AssetSource.objects.create(
        code="review-win-new",
        name="Windows",
        source_type="cloud",
        cloud_provider="aliyun",
    )
    payload = {
        "source_id": "i-windows",
        "hostname": "windows",
        "internal_ip": "10.0.0.51",
        "os_family": "windows",
    }
    record = AssetSyncRecord.objects.create(source=source, payload=[payload])
    sync_asset_source(record.pk)
    host = AssetHost.objects.get(asset_source=source)
    assert (host.connection_type, host.connection_port) == ("winrm", 5986)
    host.connection_type, host.connection_port = "ssh", 2222
    host.save()
    record = AssetSyncRecord.objects.create(source=source, payload=[payload])
    sync_asset_source(record.pk)
    host.refresh_from_db()
    assert (host.connection_type, host.connection_port) == ("ssh", 2222)


@pytest.mark.django_db
def test_preview_exposes_real_field_diffs_and_unchanged_instances():
    source = AssetSource.objects.create(
        code="review-diff", name="Diff", source_type="cloud", cloud_provider="aliyun"
    )
    host = AssetHost.objects.create(
        asset_source=source,
        source_type="cloud",
        source_id="i-1",
        hostname="web",
        internal_ip="10.0.0.1",
        asset_type="cloud_instance",
        cpu_cores=2,
        memory_mb=4096,
        external_ip="203.0.113.1",
        owner_team="manual-team",
        metadata={"business": "keep"},
    )
    item = {
        "source_id": "i-1",
        "hostname": "web",
        "internal_ip": "10.0.0.1",
        "cpu_cores": 4,
        "memory_mb": 8192,
    }
    result = preview_asset_sync(source, [item])
    assert result["update"] == 1
    changes = {change["field"]: change for change in result["rows"][0]["changes"]}
    assert changes["cpu_cores"] == {
        "field": "cpu_cores",
        "label": "CPU 核数",
        "before": 2,
        "after": 4,
    }
    assert "owner_team" not in changes and "external_ip" not in changes
    record = AssetSyncRecord.objects.create(source=source, payload=[item])
    sync_asset_source(record.pk)
    unchanged = preview_asset_sync(source, [item])
    assert unchanged["unchanged"] == 1 and unchanged["update"] == 0
    assert unchanged["rows"][0]["action"] == "unchanged"
    host.refresh_from_db()
    assert host.external_ip == "203.0.113.1" and host.owner_team == "manual-team"


@pytest.mark.django_db
def test_explicit_disk_removal_is_reported_as_a_change():
    source = AssetSource.objects.create(
        code="review-zero", name="Zero", source_type="cloud", cloud_provider="tencent"
    )
    AssetHost.objects.create(
        asset_source=source,
        source_id="ins-1",
        hostname="web",
        internal_ip="10.0.0.1",
        asset_type="cloud_instance",
        data_disk_gb=100,
    )
    result = preview_asset_sync(
        source,
        [
            {
                "source_id": "ins-1",
                "hostname": "web",
                "internal_ip": "10.0.0.1",
                "data_disk_gb": 0,
            }
        ],
    )
    assert {
        change["field"]: change["after"] for change in result["rows"][0]["changes"]
    }["data_disk_gb"] == 0


@pytest.mark.django_db
def test_sync_rejects_an_inventory_change_since_field_diff_confirmation():
    from datetime import timedelta
    from django.core import signing
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.cmdb.models import CloudImportPreview
    from apps.cmdb.sync_preview import cloud_asset_digest
    from apps.cmdb.views import AssetSourceViewSet

    source = AssetSource.objects.create(
        code="impact", name="Impact", source_type="cloud", cloud_provider="aliyun"
    )
    host = AssetHost.objects.create(
        asset_source=source,
        source_id="i-1",
        hostname="web",
        internal_ip="10.0.0.1",
        asset_type="cloud_instance",
        cpu_cores=2,
    )
    actor = get_user_model().objects.create_superuser(username="impact-admin")
    assets = [
        {
            "source_id": "i-1",
            "hostname": "web",
            "internal_ip": "10.0.0.1",
            "cpu_cores": 4,
        }
    ]
    frozen = CloudImportPreview.objects.create(
        source=source,
        created_by=actor,
        source_updated_at=source.updated_at,
        expires_at=timezone.now() + timedelta(minutes=30),
        assets=assets,
        digest=cloud_asset_digest(assets),
        status="ready",
    )
    token = signing.dumps(
        {
            "source": source.pk,
            "preview": frozen.pk,
            "digest": frozen.digest,
            "impactDigest": cloud_asset_digest(
                preview_asset_sync(source, assets)["rows"]
            ),
        },
        salt="cmdb-cloud-preview",
    )
    host.cpu_cores = 8
    host.save()
    request = APIRequestFactory().post(
        "sync-cloud",
        {"confirmationToken": token, "selectedSourceIds": ["i-1"]},
        format="json",
    )
    force_authenticate(request, user=actor)
    with patch("apps.cmdb.views.sync_asset_source.apply_async") as dispatch:
        response = AssetSourceViewSet.as_view({"post": "sync_cloud"})(
            request, pk=source.pk
        )
    assert response.status_code == 400
    dispatch.assert_not_called()
