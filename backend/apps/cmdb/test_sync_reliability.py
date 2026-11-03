from datetime import timedelta
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.cmdb.models import AssetHost, AssetSource, AssetSyncRecord
from apps.cmdb.sync_inventory import cloud_inventory_values
from apps.cmdb.tasks import sync_asset_source


@pytest.fixture
def source(db):
    from apps.cmdb.crypto import encrypt_secret
    from django.contrib.auth import get_user_model
    actor = get_user_model().objects.create_superuser(username="sync-actor")
    return AssetSource.objects.create(code="reliable-cloud", name="Cloud", source_type="cloud", cloud_provider="aliyun", regions=["cn-shanghai"], sync_actor=actor, credentials_encrypted=encrypt_secret('{"access_key_id":"id","access_key_secret":"secret"}'))


def asset(**overrides):
    return {"source_id": "i-reliable", "hostname": "web", "internal_ip": "10.0.0.1", **overrides}


def test_source_instance_identity_is_unique_even_if_name_and_ip_changed(source):
    AssetHost.objects.create(asset_source=source, source_type="cloud", **asset())
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetHost.objects.create(asset_source=source, source_type="cloud", **asset(hostname="renamed", internal_ip="10.0.0.2"))


def test_manual_hosts_with_no_instance_id_remain_independent(db):
    AssetHost.objects.create(hostname="manual-1", internal_ip="10.1.0.1")
    AssetHost.objects.create(hostname="manual-2", internal_ip="10.1.0.2")
    assert AssetHost.objects.count() == 2


def test_distinct_cloud_accounts_allow_same_name_and_private_ip(source):
    other = AssetSource.objects.create(code="other-cloud", name="Other", source_type="cloud", cloud_provider="aliyun")
    first = AssetHost.objects.create(asset_source=source, **asset())
    second = AssetHost.objects.create(asset_source=other, **asset())
    assert first.source_identity != second.source_identity


def test_manual_duplicate_is_still_rejected_by_database(db):
    AssetHost.objects.create(hostname="manual", internal_ip="10.0.1.1")
    with pytest.raises(IntegrityError), transaction.atomic():
        AssetHost.objects.create(hostname="manual", internal_ip="10.0.1.1")


def test_periodic_sync_rechecks_authorization(source):
    from apps.cmdb.sync_automation import create_sync_record
    record = create_sync_record(source, [], trigger="scheduled")
    with patch("common.auth.rbac.verify_permission", return_value=(False, "denied")), patch("apps.cmdb.cloud.collect_cloud_assets") as collect:
        sync_asset_source(record.pk)
    collect.assert_not_called()
    record.refresh_from_db()
    assert record.status == "failed" and "授权" in record.error_message


def test_duplicate_task_delivery_keeps_original_counters(source):
    record = AssetSyncRecord.objects.create(source=source, payload=[asset()])
    sync_asset_source(record.pk)
    sync_asset_source(record.pk)
    record.refresh_from_db()
    assert (record.created_count, record.updated_count, AssetHost.objects.count()) == (1, 0, 1)


@pytest.mark.parametrize("value", [1.5, True, -1, "3.5"])
def test_inventory_rejects_invalid_integer_values(source, value):
    with pytest.raises(ValueError):
        cloud_inventory_values(source, {"cpu_cores": value})


def test_explicit_empty_external_address_clears_but_missing_and_unknown_preserve(source):
    assert "external_ip" not in cloud_inventory_values(source, {})
    assert "external_ip" not in cloud_inventory_values(source, {"external_ip": None})
    assert cloud_inventory_values(source, {"external_ip": ""})["external_ip"] is None
    assert cloud_inventory_values(source, {"data_disk_gb": 0})["data_disk_gb"] == 0


def test_old_observation_cannot_overwrite_newer_inventory(source):
    now = timezone.now()
    newer = AssetSyncRecord.objects.create(source=source, observed_at=now, payload=[asset(cpu_cores=8)])
    older = AssetSyncRecord.objects.create(source=source, observed_at=now - timedelta(minutes=5), payload=[asset(cpu_cores=2)])
    sync_asset_source(newer.pk)
    sync_asset_source(older.pk)
    assert AssetHost.objects.get(source_id="i-reliable").cpu_cores == 8
    older.refresh_from_db()
    assert older.skipped_count == 1 and older.status == "succeeded"


def test_cloud_runtime_status_does_not_reactivate_retired_asset(source):
    host = AssetHost.objects.create(asset_source=source, source_type="cloud", status="retired", **asset())
    record = AssetSyncRecord.objects.create(source=source, payload=[asset(cloud_state="running")])
    sync_asset_source(record.pk)
    host.refresh_from_db()
    assert host.status == "retired" and host.cloud_state == "running"


def test_failed_collection_does_not_commit_any_region(source):
    from apps.cmdb.cloud import collect_cloud_assets, CloudCollectionError
    source.regions = ["cn-shanghai", "cn-beijing"]
    source.credentials_encrypted = "fake"
    def region_items(region, credentials):
        yield asset(region=region)
        if region == "cn-beijing":
            raise CloudCollectionError("test region failed")
    with patch("apps.cmdb.cloud.decrypt_secret", return_value='{"access_key_id":"id","access_key_secret":"secret"}'), patch("apps.cmdb.cloud._aliyun_region", side_effect=region_items):
        with pytest.raises(CloudCollectionError, match="failed"):
            collect_cloud_assets(source)
    assert not AssetHost.objects.exists()


def test_periodic_sync_is_opt_in_and_deduplicated(source, django_capture_on_commit_callbacks):
    from apps.cmdb.sync_automation import queue_due_cloud_syncs
    now = timezone.now()
    assert queue_due_cloud_syncs(now) == 0
    source.sync_interval_minutes = 5
    source.save()
    with patch("apps.cmdb.tasks.sync_asset_source.apply_async", return_value=SimpleNamespace(id="test-sync-task")) as dispatch, django_capture_on_commit_callbacks(execute=True):
        assert queue_due_cloud_syncs(now) == 1
        assert queue_due_cloud_syncs(now) == 0
    assert dispatch.call_count == 1
    record = AssetSyncRecord.objects.get(source=source)
    assert record.trigger == "scheduled" and not record.collection_scope["complete"]
    record.status = "succeeded"
    record.save()
    assert queue_due_cloud_syncs(now + timedelta(minutes=4)) == 0
    assert queue_due_cloud_syncs(now + timedelta(minutes=5)) == 1


def test_periodic_failed_read_never_writes_partial_assets(source):
    from apps.cmdb.sync_automation import create_sync_record
    from apps.cmdb.cloud import CloudCollectionError
    record = create_sync_record(source, [], trigger="scheduled")
    with patch("apps.cmdb.cloud.collect_cloud_assets", side_effect=CloudCollectionError("region failed")):
        sync_asset_source(record.pk)
    record.refresh_from_db()
    source.refresh_from_db()
    assert record.status == "failed" and not record.collection_scope["complete"]
    assert source.last_synced_at is None and not AssetHost.objects.exists()


def test_periodic_success_records_scope_changes_and_manual_state(source):
    from apps.cmdb.sync_automation import create_sync_record
    record = create_sync_record(source, [], trigger="scheduled")
    with patch("apps.cmdb.cloud.collect_cloud_assets", return_value=[asset(cpu_cores=4, cloud_state="stopped")]):
        sync_asset_source(record.pk)
    record.refresh_from_db()
    host = AssetHost.objects.get(source_id="i-reliable")
    assert record.status == "succeeded" and record.collection_scope["complete"]
    assert record.changes[0]["action"] == "create"
    assert host.status == "active" and host.cloud_state == "stopped"


def test_sync_failure_notification_uses_snapshot_and_existing_retry_delivery(source):
    from apps.automation.models import NotificationChannel, NotificationTemplate, NotificationRecord
    from apps.cmdb.sync_automation import create_sync_record, fail_sync, queue_sync_failure_alert
    from apps.jobs.alerts import deliver_alert
    channel = NotificationChannel.objects.create(name="sync-channel", channel_type="webhook")
    template = NotificationTemplate.objects.create(name="sync-template", code="sync-template", channel=channel,
        subject_template="{{ title }}", body_template="{{ sync.sourceName }} {{ sync.errorMessage }}")
    source.sync_failure_alert = {"templateId": template.pk, "receivers": ""}
    source.save()
    record = create_sync_record(source, [], trigger="scheduled")
    fail_sync(record, "region denied")
    queue_sync_failure_alert(record)
    alert = NotificationRecord.objects.get(alert_key=f"cmdb-sync-failure:{record.pk}")
    template.body_template = "changed"
    template.save()
    with patch("apps.jobs.alerts.send_notification") as send:
        assert deliver_alert(alert.pk)
    assert send.call_args.args[0].body_template == "{{ sync.sourceName }} {{ sync.errorMessage }}"
    assert send.call_args.args[1]["sync"]["sourceName"] == source.name
    assert NotificationRecord.objects.count() == 1


def test_account_sync_configuration_is_validated(source):
    from apps.cmdb.serializers import AssetSourceSerializer
    invalid = AssetSourceSerializer(source, data={"sync_interval_minutes": 1}, partial=True)
    assert not invalid.is_valid()
    valid = AssetSourceSerializer(source, data={"sync_interval_minutes": 5}, partial=True)
    assert valid.is_valid(), valid.errors


def test_legacy_identity_check_stops_before_merging_assets(source):
    from importlib import import_module
    from types import SimpleNamespace
    from django.apps import apps
    migration = import_module("apps.cmdb.migrations.0013_assethost_cloud_state_assethost_last_observed_at_and_more")
    AssetHost.objects.bulk_create([
        AssetHost(asset_source=source, source_id="legacy", hostname="one", internal_ip="10.2.0.1"),
        AssetHost(asset_source=source, source_id="legacy", hostname="two", internal_ip="10.2.0.2"),
    ])
    with pytest.raises(RuntimeError, match="ID"):
        migration.check_identities(apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
    assert AssetHost.objects.count() == 2


def test_duplicate_cloud_response_is_rejected_before_auto_sync(source):
    from apps.cmdb.cloud import collect_cloud_assets, CloudCollectionError
    with patch("apps.cmdb.cloud._aliyun_region", return_value=iter([asset(), asset()])):
        with pytest.raises(CloudCollectionError, match="重复"):
            collect_cloud_assets(source)


def test_confirming_valid_row_never_queues_duplicate_invalid_row(source):
    from django.core import signing
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.cmdb.models import CloudImportPreview
    from apps.cmdb.sync_preview import cloud_asset_digest, preview_asset_sync
    from apps.cmdb.views import AssetSourceViewSet
    assets = [asset(), asset(hostname="duplicate", internal_ip="10.0.0.2")]
    frozen = CloudImportPreview.objects.create(source=source, created_by=source.sync_actor,
        source_updated_at=source.updated_at, assets=assets, digest=cloud_asset_digest(assets),
        status="ready", expires_at=timezone.now() + timedelta(minutes=30))
    token = signing.dumps({"source": source.pk, "preview": frozen.pk, "digest": frozen.digest,
        "impactDigest": cloud_asset_digest(preview_asset_sync(source, assets)["rows"])}, salt="cmdb-cloud-preview")
    request = APIRequestFactory().post("/sync-cloud", {"confirmationToken": token, "selectedSourceIds": ["i-reliable"]}, format="json")
    force_authenticate(request, user=source.sync_actor)
    response = AssetSourceViewSet.as_view({"post": "sync_cloud"})(request, pk=source.pk)
    assert response.status_code == 200
    assert AssetSyncRecord.objects.get(source=source).payload == [assets[0]]


def test_old_queued_record_without_observed_time_remains_compatible(source):
    record = AssetSyncRecord.objects.create(source=source, observed_at=None, payload=[asset()])
    sync_asset_source(record.pk)
    record.refresh_from_db()
    assert record.status == "succeeded" and record.observed_at is None
    assert AssetHost.objects.get(source_id="i-reliable").last_observed_at == record.created_at
