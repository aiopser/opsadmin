import pytest

from apps.automation.models import NotificationChannel
from apps.automation.serializers import NotificationChannelSerializer


@pytest.mark.django_db
def test_notification_channel_encrypts_url_and_hides_secret():
    serializer = NotificationChannelSerializer(
        data={
            "name": "Feishu operations",
            "channel_type": NotificationChannel.ChannelType.FEISHU,
            "secret": "https://example.test/robot/token",
        }
    )
    assert serializer.is_valid(), serializer.errors
    channel = serializer.save()
    assert "https://example.test/robot/token" not in channel.secret_encrypted
    assert "secret_encrypted" not in serializer.data
    assert "https://example.test/robot/token" not in str(serializer.data)


@pytest.mark.parametrize("secret", ["", "http://example.test/robot", "not-a-url"])
def test_notification_channel_rejects_missing_or_insecure_url(secret):
    serializer = NotificationChannelSerializer(
        data={
            "name": "Operations",
            "channel_type": NotificationChannel.ChannelType.DINGTALK,
            "secret": secret,
        }
    )
    assert not serializer.is_valid()
    assert "secret" in serializer.errors


@pytest.mark.django_db
def test_notification_channel_encrypts_signing_secret():
    serializer = NotificationChannelSerializer(
        data={
            "name": "DingTalk operations",
            "channel_type": NotificationChannel.ChannelType.DINGTALK,
            "secret": "https://example.test/robot/token",
            "signing_secret": "SEC-signing-value",
        }
    )
    assert serializer.is_valid(), serializer.errors
    channel = serializer.save()
    assert channel.signing_secret_encrypted
    assert "SEC-signing-value" not in channel.signing_secret_encrypted
    assert "signing_secret_encrypted" not in serializer.data
    assert serializer.data["hasSigningSecret"] is True


def test_notification_channel_rejects_signing_secret_for_wecom():
    serializer = NotificationChannelSerializer(
        data={
            "name": "WeCom operations",
            "channel_type": NotificationChannel.ChannelType.WECOM,
            "secret": "https://example.test/robot/token",
            "signing_secret": "SEC-signing-value",
        }
    )
    assert not serializer.is_valid()
    assert "signing_secret" in serializer.errors
