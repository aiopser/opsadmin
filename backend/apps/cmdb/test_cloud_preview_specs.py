from types import SimpleNamespace

import pytest

from apps.cmdb.models import AssetSource
from apps.cmdb.sync_inventory import cloud_inventory_values
from apps.cmdb.sync_preview import preview_asset_sync


def test_legacy_cloud_inventory_keeps_region_from_metadata():
    source = SimpleNamespace(cloud_provider="aliyun")
    values = cloud_inventory_values(source, {"metadata": {"region": "cn-shanghai"}})
    assert values["region"] == "cn-shanghai"
    explicit = cloud_inventory_values(source, {
        "region": "cn-beijing", "metadata": {"region": "cn-shanghai"},
    })
    assert explicit["region"] == "cn-beijing"


@pytest.mark.django_db
def test_preview_specs_use_same_normalized_values_as_synchronization():
    source = AssetSource.objects.create(
        code="preview-specs", name="Cloud", source_type="cloud", cloud_provider="aliyun",
    )
    preview = preview_asset_sync(source, [{
        "sourceId": "i-preview", "hostname": "web", "internalIp": "10.0.0.1",
        "cpuCores": 4, "memoryMb": 8192, "systemDiskGb": 40, "dataDiskGb": 0,
        "metadata": {"region": "cn-shanghai"},
    }])
    assert preview["rows"][0]["specs"] == {
        "cpu_cores": 4, "memory_mb": 8192, "system_disk_gb": 40,
        "data_disk_gb": 0, "region": "cn-shanghai",
    }
