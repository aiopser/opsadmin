from datetime import timedelta

import pytest
from django.utils import timezone

from .models import NotificationRecord
from .notification_history import (
    DEFAULT_RETENTION_DAYS,
    get_history_settings,
    purge_notification_history,
    save_history_settings,
)


def _create_record(*, status, days_ago, alert_key=None):
    return NotificationRecord.objects.create(
        status=status,
        sent_at=timezone.now() - timedelta(days=days_ago),
        alert_key=alert_key,
    )


@pytest.mark.django_db
def test_history_settings_defaults_and_roundtrip():
    assert get_history_settings()["retentionDays"] == DEFAULT_RETENTION_DAYS
    assert save_history_settings({"retentionDays": 30})["retentionDays"] == 30
    assert get_history_settings()["retentionDays"] == 30


@pytest.mark.django_db
def test_history_settings_rejects_invalid_retention():
    with pytest.raises(ValueError):
        save_history_settings({"retentionDays": 0})
    with pytest.raises(ValueError):
        save_history_settings({"retentionDays": "abc"})


@pytest.mark.django_db
def test_purge_only_deletes_expired_success_records():
    expired_success = _create_record(
        status=NotificationRecord.Status.SUCCESS, days_ago=40
    )
    success_without_sent_at = NotificationRecord.objects.create(
        status=NotificationRecord.Status.SUCCESS
    )
    recent_success = _create_record(
        status=NotificationRecord.Status.SUCCESS, days_ago=5
    )
    expired_failed = _create_record(
        status=NotificationRecord.Status.FAILED, days_ago=40
    )
    expired_alert = _create_record(
        status=NotificationRecord.Status.SUCCESS,
        days_ago=40,
        alert_key="alert:demo",
    )

    preview = purge_notification_history(dry_run=True, retention_days=30)
    assert preview == {"count": 1, "deleted": 0, "dryRun": True}

    result = purge_notification_history(retention_days=30)
    assert result["deleted"] == 1

    remaining = set(NotificationRecord.objects.values_list("pk", flat=True))
    assert remaining == {
        success_without_sent_at.pk,
        recent_success.pk,
        expired_failed.pk,
        expired_alert.pk,
    }
