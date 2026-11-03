from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.email_settings import (
    check_email_connection,
    get_email_delivery_config,
    get_email_settings,
    save_email_settings,
    send_test_email,
)
from apps.automation.models import NotificationChannel, NotificationTemplate
from apps.automation.views import (
    NotificationEmailConnectionTestView,
    NotificationEmailSettingsView,
)
from apps.jobs.node_executors import send_notification
from apps.permission.models import SystemConfig

SETTINGS_PAYLOAD = {
    "name": "默认邮件服务器",
    "description": "系统通知发信",
    "fromEmail": "noreply@example.test",
    "titlePrefix": "DevOps消息通知：",
    "protocol": "smtp",
    "host": "smtp.example.test",
    "port": 587,
    "timeout": 10,
    "useTls": True,
    "username": "ops@example.test",
    "password": "top-secret",
}


@pytest.mark.django_db
def test_saved_settings_hide_password():
    data = save_email_settings(SETTINGS_PAYLOAD)

    assert data == {
        "name": "默认邮件服务器",
        "description": "系统通知发信",
        "fromEmail": "noreply@example.test",
        "titlePrefix": "DevOps消息通知：",
        "protocol": "smtp",
        "host": "smtp.example.test",
        "port": 587,
        "timeout": 10,
        "useTls": True,
        "username": "ops@example.test",
        "hasPassword": True,
        "configured": True,
    }
    assert "password" not in data


@pytest.mark.django_db
def test_password_is_encrypted_at_rest():
    save_email_settings(SETTINGS_PAYLOAD)

    stored = SystemConfig.objects.get(
        config_key="notification.email.password"
    ).config_value

    assert stored
    assert "top-secret" not in stored
    assert get_email_delivery_config()["password"] == "top-secret"


@pytest.mark.django_db
def test_blank_password_keeps_existing_secret():
    save_email_settings(SETTINGS_PAYLOAD)
    save_email_settings({**SETTINGS_PAYLOAD, "password": ""})

    assert get_email_delivery_config()["password"] == "top-secret"


@pytest.mark.django_db
def test_secure_smtp_ignores_starttls():
    data = save_email_settings(
        {**SETTINGS_PAYLOAD, "protocol": "secure_smtp", "port": 465, "useTls": True}
    )

    assert data["protocol"] == "secure_smtp"
    assert data["useTls"] is False
    assert get_email_delivery_config()["useSsl"] is True


@pytest.mark.django_db
def test_invalid_protocol_is_rejected():
    with pytest.raises(ValueError):
        save_email_settings({**SETTINGS_PAYLOAD, "protocol": "pop3"})


@pytest.mark.django_db
def test_missing_required_fields_are_rejected():
    with pytest.raises(ValueError):
        save_email_settings({**SETTINGS_PAYLOAD, "name": ""})
    with pytest.raises(ValueError):
        save_email_settings({**SETTINGS_PAYLOAD, "fromEmail": ""})
    with pytest.raises(ValueError):
        save_email_settings({**SETTINGS_PAYLOAD, "host": ""})


@pytest.mark.django_db
def test_invalid_timeout_is_rejected():
    with pytest.raises(ValueError):
        save_email_settings({**SETTINGS_PAYLOAD, "timeout": -1})


@pytest.mark.django_db
def test_delivery_config_is_none_without_host():
    assert get_email_delivery_config() is None


@pytest.mark.django_db
def test_legacy_ssl_setting_maps_to_secure_smtp():
    SystemConfig.objects.create(
        config_key="notification.email.host",
        config_name="通知邮件服务器:host",
        config_value="smtp.example.test",
        config_group="notification",
    )
    SystemConfig.objects.create(
        config_key="notification.email.use_ssl",
        config_name="通知邮件服务器:use_ssl",
        config_value="true",
        config_group="notification",
    )

    assert get_email_settings()["protocol"] == "secure_smtp"
    assert get_email_delivery_config()["useSsl"] is True


@pytest.mark.django_db
def test_send_test_email_requires_configuration():
    with pytest.raises(ValueError):
        send_test_email("ops@example.test")


@pytest.mark.django_db
def test_send_test_email_uses_saved_settings():
    save_email_settings(SETTINGS_PAYLOAD)

    with (
        patch("django.core.mail.get_connection") as get_connection,
        patch("django.core.mail.send_mail") as send_mail,
    ):
        send_test_email("ops@example.test")

    kwargs = get_connection.call_args.kwargs
    assert kwargs["host"] == "smtp.example.test"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "ops@example.test"
    assert kwargs["password"] == "top-secret"
    assert kwargs["use_tls"] is True
    assert kwargs["use_ssl"] is False
    assert kwargs["timeout"] == 10
    assert send_mail.call_args.kwargs["connection"] is get_connection.return_value
    assert send_mail.call_args.args[0] == "DevOps消息通知：DevOps 平台测试邮件"


@pytest.mark.django_db
def test_connection_test_uses_form_values():
    with patch("django.core.mail.get_connection") as get_connection:
        check_email_connection(
            {
                "protocol": "secure_smtp",
                "host": "smtp.example.test",
                "port": 465,
                "timeout": 0,
                "username": "ops@example.test",
                "password": "top-secret",
                "useTls": True,
            }
        )

    kwargs = get_connection.call_args.kwargs
    assert kwargs["host"] == "smtp.example.test"
    assert kwargs["port"] == 465
    assert kwargs["password"] == "top-secret"
    assert kwargs["use_tls"] is False
    assert kwargs["use_ssl"] is True
    assert kwargs["timeout"] is None
    get_connection.return_value.open.assert_called_once_with()
    get_connection.return_value.close.assert_called_once_with()


@pytest.mark.django_db
def test_connection_test_reuses_saved_password_when_blank():
    save_email_settings(SETTINGS_PAYLOAD)

    with patch("django.core.mail.get_connection") as get_connection:
        check_email_connection(
            {
                "protocol": "smtp",
                "host": "smtp.example.test",
                "port": 587,
                "timeout": 10,
                "username": "ops@example.test",
                "password": "",
                "useTls": True,
            }
        )

    assert get_connection.call_args.kwargs["password"] == "top-secret"


@pytest.mark.django_db
def test_connection_test_requires_host():
    with pytest.raises(ValueError):
        check_email_connection(
            {"protocol": "smtp", "host": "", "port": 25, "timeout": 10}
        )


@pytest.mark.django_db
def test_notification_email_channel_uses_saved_settings():
    save_email_settings(SETTINGS_PAYLOAD)
    channel = NotificationChannel.objects.create(
        name="邮件通知",
        channel_type=NotificationChannel.ChannelType.EMAIL,
    )
    template = NotificationTemplate.objects.create(
        name="失败告警",
        code="test.email.alert",
        channel=channel,
        subject_template="{{ title }}",
        body_template="运行失败：{{ title }}",
    )

    with (
        patch("django.core.mail.get_connection") as get_connection,
        patch("django.core.mail.send_mail") as send_mail,
    ):
        send_mail.return_value = 1
        send_notification(
            template,
            {"title": "hello"},
            overrides={"receivers": "ops@example.test"},
        )

    assert get_connection.call_args.kwargs["host"] == "smtp.example.test"
    assert send_mail.call_args.kwargs["connection"] is get_connection.return_value
    assert send_mail.call_args.args[0] == "DevOps消息通知：hello"
    assert send_mail.call_args.args[3] == ["ops@example.test"]


@pytest.mark.django_db
def test_settings_api_roundtrip():
    user = get_user_model().objects.create_user(
        username="settings-admin",
        password="not-used",
        is_superuser=True,
    )
    request = APIRequestFactory().put(
        "/api/v1/notifications/email-settings",
        SETTINGS_PAYLOAD,
        format="json",
    )
    force_authenticate(request, user=user)

    response = NotificationEmailSettingsView.as_view()(request)

    assert response.status_code == 200, response.data
    assert response.data["data"]["host"] == "smtp.example.test"
    assert response.data["data"]["hasPassword"] is True
    assert "password" not in response.data["data"]


@pytest.mark.django_db
def test_connection_test_api():
    user = get_user_model().objects.create_user(
        username="settings-admin",
        password="not-used",
        is_superuser=True,
    )
    request = APIRequestFactory().post(
        "/api/v1/notifications/email-settings/test-connection",
        SETTINGS_PAYLOAD,
        format="json",
    )
    force_authenticate(request, user=user)

    with patch("django.core.mail.get_connection"):
        response = NotificationEmailConnectionTestView.as_view()(request)

    assert response.status_code == 200, response.data
    assert response.data["data"] == {"connected": True}
