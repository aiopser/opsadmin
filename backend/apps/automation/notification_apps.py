"""企业微信、钉钉、飞书应用凭据设置。

与邮件服务器一致：配置以 SystemConfig 键值存储（分组 notification），
Secret 使用 Fernet 加密，接口只返回「是否已配置」而不回显明文。
"""

import requests

from apps.cmdb.crypto import decrypt_secret, encrypt_secret
from apps.permission.models import SystemConfig

CONFIG_GROUP = "notification"

PROVIDER_WECOM = "wecom"
PROVIDER_DINGTALK = "dingtalk"
PROVIDER_FEISHU = "feishu"
PROVIDERS = (PROVIDER_WECOM, PROVIDER_DINGTALK, PROVIDER_FEISHU)

SPECS = {
    PROVIDER_WECOM: {
        "prefix": "notification.wecom.",
        "id_key": "corp_id",
        "id_label": "CorpID",
        "agent_key": "agent_id",
        "agent_required": True,
        "default_api_base": "https://qyapi.weixin.qq.com",
        "secret_key": "secret",
    },
    PROVIDER_DINGTALK: {
        "prefix": "notification.dingtalk.",
        "id_key": "app_key",
        "id_label": "AppKey",
        "agent_key": "agent_id",
        "agent_required": False,
        "default_api_base": "https://oapi.dingtalk.com",
        "secret_key": "secret",
    },
    PROVIDER_FEISHU: {
        "prefix": "notification.feishu.",
        "id_key": "app_id",
        "id_label": "AppID",
        "agent_key": None,
        "agent_required": False,
        "default_api_base": "https://open.feishu.cn",
        "secret_key": "secret",
    },
}


def _get_spec(provider: str) -> dict:
    spec = SPECS.get(provider)
    if spec is None:
        raise ValueError("不支持的应用类型")
    return spec


def _config_key(provider: str, name: str) -> str:
    return f"{SPECS[provider]['prefix']}{name}"


def _load_values(provider: str) -> dict:
    spec = _get_spec(provider)
    names = [spec["id_key"], "api_base", spec["secret_key"]]
    if spec["agent_key"]:
        names.append(spec["agent_key"])
    keys = [_config_key(provider, name) for name in names]
    return {
        item.config_key: item.config_value
        for item in SystemConfig.objects.filter(config_key__in=keys)
    }


def _normalize_api_base(raw: str | None, default: str) -> str:
    value = str(raw or "").strip().rstrip("/")
    if not value:
        return default
    if not value.startswith(("http://", "https://")):
        raise ValueError("API 地址必须以 http:// 或 https:// 开头")
    return value


def get_app_settings(provider: str) -> dict:
    """读取应用配置，Secret 仅以 hasSecret 标识。"""
    spec = _get_spec(provider)
    stored = _load_values(provider)
    app_id = stored.get(_config_key(provider, spec["id_key"]), "")
    agent_id = ""
    if spec["agent_key"]:
        agent_id = stored.get(_config_key(provider, spec["agent_key"]), "")
    return {
        "provider": provider,
        "appId": app_id,
        "agentId": agent_id,
        "apiBase": stored.get(_config_key(provider, "api_base"))
        or spec["default_api_base"],
        "hasSecret": bool(stored.get(_config_key(provider, spec["secret_key"]))),
        "configured": bool(app_id),
    }


def save_app_settings(provider: str, payload: dict) -> dict:
    """保存应用配置；Secret 留空表示保持原值。"""
    spec = _get_spec(provider)
    app_id = str(payload.get("appId") or "").strip()
    agent_id = str(payload.get("agentId") or "").strip() if spec["agent_key"] else ""
    api_base = _normalize_api_base(payload.get("apiBase"), spec["default_api_base"])
    if not app_id:
        raise ValueError(f"请输入{spec['id_label']}")
    if spec["agent_required"] and not agent_id:
        raise ValueError("请输入 AgentId")

    secret = str(payload.get("appSecret") or "")
    stored = _load_values(provider)
    if not secret and not stored.get(_config_key(provider, spec["secret_key"])):
        raise ValueError("请输入 Secret")

    values = {spec["id_key"]: app_id, "api_base": api_base}
    if spec["agent_key"]:
        values[spec["agent_key"]] = agent_id
    for name, value in values.items():
        SystemConfig.objects.update_or_create(
            config_key=_config_key(provider, name),
            defaults={
                "config_name": f"通知应用:{provider}:{name}",
                "config_value": value,
                "config_group": CONFIG_GROUP,
                "is_system": True,
            },
        )
    if secret:
        SystemConfig.objects.update_or_create(
            config_key=_config_key(provider, spec["secret_key"]),
            defaults={
                "config_name": f"通知应用:{provider}:secret",
                "config_value": encrypt_secret(secret),
                "config_group": CONFIG_GROUP,
                "is_system": True,
            },
        )
    return get_app_settings(provider)


def _request_json(method: str, url: str, **kwargs) -> dict:
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
        response.raise_for_status()
        return response.json()
    except ValueError as exc:
        raise ValueError("服务返回的内容不是有效的 JSON") from exc
    except requests.Timeout as exc:
        raise ValueError("连接超时，请检查 API 地址与网络") from exc
    except requests.RequestException as exc:
        raise ValueError("连接失败，请检查 API 地址与网络连通性") from exc


def _check_wecom(app_id: str, secret: str, api_base: str) -> None:
    data = _request_json(
        "GET",
        f"{api_base}/cgi-bin/gettoken",
        params={"corpid": app_id, "corpsecret": secret},
    )
    if data.get("errcode") != 0:
        raise ValueError(f"企业微信返回错误：{data.get('errmsg') or data.get('errcode')}")


def _check_dingtalk(app_id: str, secret: str, api_base: str) -> None:
    data = _request_json(
        "GET",
        f"{api_base}/gettoken",
        params={"appkey": app_id, "appsecret": secret},
    )
    if data.get("errcode") != 0:
        raise ValueError(f"钉钉返回错误：{data.get('errmsg') or data.get('errcode')}")


def _check_feishu(app_id: str, secret: str, api_base: str) -> None:
    data = _request_json(
        "POST",
        f"{api_base}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": secret},
    )
    if data.get("code") != 0 or not data.get("tenant_access_token"):
        raise ValueError(f"飞书返回错误：{data.get('msg') or data.get('code')}")


def check_app_connection(provider: str, payload: dict) -> None:
    """使用表单值测试应用凭据；Secret 留空时使用已保存的 Secret。"""
    spec = _get_spec(provider)
    app_id = str(payload.get("appId") or "").strip()
    api_base = _normalize_api_base(payload.get("apiBase"), spec["default_api_base"])
    if not app_id:
        raise ValueError(f"请输入{spec['id_label']}")

    secret = str(payload.get("appSecret") or "")
    if not secret:
        stored = _load_values(provider)
        token = stored.get(_config_key(provider, spec["secret_key"]), "")
        secret = decrypt_secret(token) if token else ""
    if not secret:
        raise ValueError("请输入 Secret")

    if provider == PROVIDER_WECOM:
        _check_wecom(app_id, secret, api_base)
    elif provider == PROVIDER_DINGTALK:
        _check_dingtalk(app_id, secret, api_base)
    else:
        _check_feishu(app_id, secret, api_base)
