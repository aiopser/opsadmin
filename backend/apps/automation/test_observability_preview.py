import pytest

from apps.automation.notification_preview import (
    notification_catalog,
    preview_notification,
)


@pytest.mark.parametrize(
    ("scenario", "expression"),
    [("security", "advisory.title")],
)
def test_observability_notification_preview(scenario, expression):
    from apps.automation.serializers import NotificationPreviewSerializer

    serializer = NotificationPreviewSerializer(data={"scenario": scenario})
    assert serializer.is_valid(), serializer.errors
    catalog = notification_catalog(scenario)
    assert "{{ " + expression + " }}" in {
        item["expression"] for item in catalog["variables"]
    }
    assert "delivery" not in catalog["sampleContext"]
    result = preview_notification(
        scenario=scenario,
        subject="{{ title }}",
        body="{{ " + expression + " }}",
        receivers="",
    )
    assert result["valid"]
    assert result["subject"] and result["body"]
