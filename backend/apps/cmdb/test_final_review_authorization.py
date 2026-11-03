"""Cloud inventory workers honor the responsible user's current authorization."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from .models import AssetHost, AssetSource
from .sync_automation import create_sync_record


@pytest.mark.django_db
@pytest.mark.parametrize("when", ["before_worker", "during_collection"])
def test_suspended_scheduled_sync_actor_cannot_import(when) -> None:
    from .tasks import sync_asset_source

    actor = get_user_model().objects.create_superuser(username="final-sync-owner")
    source = AssetSource.objects.create(
        code="final-sync",
        name="Cloud",
        source_type="cloud",
        cloud_provider="aliyun",
        regions=["cn-shanghai"],
        sync_actor=actor,
    )
    record = create_sync_record(source, [], trigger="scheduled")
    item = {
        "source_id": "i-final-review",
        "hostname": "final-review",
        "internal_ip": "10.8.0.1",
        "os_family": "linux",
        "region": "cn-shanghai",
        "cloud_state": "running",
    }

    def collect(*args):
        if when == "during_collection":
            get_user_model().objects.filter(pk=actor.pk).update(job_status=False)
        return [item]

    if when == "before_worker":
        get_user_model().objects.filter(pk=actor.pk).update(job_status=False)
    with patch("apps.cmdb.cloud.collect_cloud_assets", side_effect=collect):
        sync_asset_source(record.pk)
    assert not AssetHost.objects.filter(source_id=item["source_id"]).exists()
    record.refresh_from_db()
    assert record.status == "failed"
