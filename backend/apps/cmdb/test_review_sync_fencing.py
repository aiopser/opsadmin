from unittest.mock import patch

from apps.cmdb.models import AssetHost, AssetSyncRecord
from apps.cmdb.tasks import sync_asset_source
from apps.cmdb.test_sync_reliability import source, asset


def test_sync_recovery_during_last_host_write_keeps_failed_terminal_state(source):
    record = AssetSyncRecord.objects.create(source=source, payload=[asset()])
    original = AssetHost.save

    def save_and_recover(host, *args, **kwargs):
        result = original(host, *args, **kwargs)
        AssetSyncRecord.objects.filter(pk=record.pk).update(
            status="failed", error_message="recovered timeout"
        )
        return result

    with patch.object(AssetHost, "save", save_and_recover):
        result = sync_asset_source(record.pk)
    record.refresh_from_db()
    source.refresh_from_db()
    assert record.status == "failed" and record.error_message == "recovered timeout"
    assert source.last_synced_at is None
    assert result.get("claimed") is False


def test_stale_sync_failure_cannot_overwrite_success(source):
    from apps.cmdb.sync_automation import fail_sync

    record = AssetSyncRecord.objects.create(source=source, status="running")
    AssetSyncRecord.objects.filter(pk=record.pk).update(status="succeeded")
    fail_sync(record, "late cloud error")
    record.refresh_from_db()
    assert record.status == "succeeded" and record.error_message == ""
