from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.notification_apps import (
    check_app_connection,
    get_app_settings,
    save_app_settings,
)
from apps.automation.views import WecomSettingsView
from apps.permission.models import SystemConfig

WECOM_PAYLOAD = {
    "appId": "corp-demo",
    "agentId": "1000002",
    "apiBase": "https://qyapi.weixin.qq.com/",
    "appSecret": "wecom-secret",
}

DINGTALK_PAYLOAD = {
    "appId": "ding-app-key",
    "agentId": "",
    "apiBase": "https://oapi.dingtalk.com",
    "appSecret": "ding-secret",
}

FEISHU_PAYLOAD = {
    "appId": "cli-demo",
    "agentId": "",
    "apiBase": "https://open.feishu.cn",
    "appSecret": "feishu-secret",
}


@pytest.mark.django_db
def test_wecom_settings_hide_secret():
    data = save_app_settings("wecom", WECOM_PAYLOAD)

    assert data == {
        "provider": "wecom",
        "appId": "corp-demo",
        "agentId": "1000002",
        "apiBase": "https://qyapi.weixin.qq.com",
        "hasSecret": True,
        "configured": True,
    }
    assert "appSecret" not in data


@pytest.mark.django_db
def test_secret_is_encrypted_at_rest():
    save_app_settings("wecom", WECOM_PAYLOAD)

    stored = SystemConfig.objects.get(
        config_key="notification.wecom.secret"
    ).config_value

    assert "wecom-secret" not in stored


@pytest.mark.django_db
def test_blank_secret_keeps_existing_value():
    save_app_settings("feishu", FEISHU_PAYLOAD)
    data = save_app_settings("feishu", {**FEISHU_PAYLOAD, "appSecret": ""})

    assert data["hasSecret"] is True
    assert data["appId"] == "cli-demo"


@pytest.mark.django_db
def test_first_save_requires_secret():
    with pytest.raises(ValueError):
        save_app_settings("wecom", {**WECOM_PAYLOAD, "appSecret": ""})


@pytest.mark.django_db
def test_wecom_requires_agent_id():
    with pytest.raises(ValueError):
        save_app_settings("wecom", {**WECOM_PAYLOAD, "agentId": ""})


@pytest.mark.django_db
def test_api_base_must_use_http_scheme():
    with pytest.raises(ValueError):
        save_app_settings("wecom", {**WECOM_PAYLOAD, "apiBase": "qyapi.weixin.qq.com"})


@pytest.mark.django_db
def test_unconfigured_provider_returns_defaults():
    data = get_app_settings("dingtalk")

    assert data == {
        "provider": "dingtalk",
        "appId": "",
        "agentId": "",
        "apiBase": "https://oapi.dingtalk.com",
        "hasSecret": False,
        "configured": False,
    }


@pytest.mark.django_db
def test_wecom_connection_success():
    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {"errcode": 0, "access_token": "token"}

        check_app_connection("wecom", WECOM_PAYLOAD)

    args, kwargs = request.call_args
    assert args == ("GET", "https://qyapi.weixin.qq.com/cgi-bin/gettoken")
    assert kwargs["params"] == {"corpid": "corp-demo", "corpsecret": "wecom-secret"}


@pytest.mark.django_db
def test_wecom_connection_business_error():
    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {
            "errcode": 40013,
            "errmsg": "invalid corpid",
        }

        with pytest.raises(ValueError, match="invalid corpid"):
            check_app_connection("wecom", WECOM_PAYLOAD)


@pytest.mark.django_db
def test_dingtalk_connection_success():
    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {"errcode": 0, "access_token": "token"}

        check_app_connection("dingtalk", DINGTALK_PAYLOAD)

    args, kwargs = request.call_args
    assert args == ("GET", "https://oapi.dingtalk.com/gettoken")
    assert kwargs["params"] == {
        "appkey": "ding-app-key",
        "appsecret": "ding-secret",
    }


@pytest.mark.django_db
def test_feishu_connection_success():
    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {
            "code": 0,
            "tenant_access_token": "token",
        }

        check_app_connection("feishu", FEISHU_PAYLOAD)

    args, kwargs = request.call_args
    assert args == (
        "POST",
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    )
    assert kwargs["json"] == {
        "app_id": "cli-demo",
        "app_secret": "feishu-secret",
    }


@pytest.mark.django_db
def test_feishu_connection_failure():
    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {
            "code": 10003,
            "msg": "invalid app_secret",
        }

        with pytest.raises(ValueError, match="invalid app_secret"):
            check_app_connection("feishu", FEISHU_PAYLOAD)


@pytest.mark.django_db
def test_connection_reuses_saved_secret():
    save_app_settings("feishu", FEISHU_PAYLOAD)

    with patch("apps.automation.notification_apps.requests.request") as request:
        request.return_value.json.return_value = {
            "code": 0,
            "tenant_access_token": "token",
        }

        check_app_connection("feishu", {**FEISHU_PAYLOAD, "appSecret": ""})

    assert request.call_args.kwargs["json"]["app_secret"] == "feishu-secret"


@pytest.mark.django_db
def test_settings_api_roundtrip():
    user = get_user_model().objects.create_user(
        username="settings-admin",
        password="not-used",
        is_superuser=True,
    )
    request = APIRequestFactory().put(
        "/api/v1/notifications/wecom-settings",
        WECOM_PAYLOAD,
        format="json",
    )
    force_authenticate(request, user=user)

    response = WecomSettingsView.as_view()(request)

    assert response.status_code == 200, response.data
    assert response.data["data"]["appId"] == "corp-demo"
    assert response.data["data"]["hasSecret"] is True
    assert "appSecret" not in response.data["data"]
