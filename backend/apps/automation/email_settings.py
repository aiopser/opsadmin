"""SMTP 邮件服务器设置。

配置以 SystemConfig 键值存储（分组 notification），密码使用 Fernet 加密，
接口只返回「是否已配置」而不回显明文。未配置服务器地址时，发送逻辑回退
到部署环境变量（EMAIL_HOST 等）。
"""

from apps.cmdb.crypto import decrypt_secret, encrypt_secret
from apps.permission.models import SystemConfig

CONFIG_GROUP = "notification"
KEY_PREFIX = "notification.email."

PROTOCOL_SMTP = "smtp"
PROTOCOL_SECURE_SMTP = "secure_smtp"
PROTOCOLS = (PROTOCOL_SMTP, PROTOCOL_SECURE_SMTP)

DEFAULT_TITLE_PREFIX = "DevOps消息通知："
DEFAULT_SETTINGS = {
    "name": "",
    "description": "",
    "from_email": "",
    "title_prefix": DEFAULT_TITLE_PREFIX,
    "protocol": PROTOCOL_SMTP,
    "host": "",
    "port": 25,
    "timeout": 10,
    "use_tls": False,
    "username": "",
}

_STORED_KEYS = (
    "name",
    "description",
    "from_email",
    "title_prefix",
    "protocol",
    "host",
    "port",
    "timeout",
    "use_tls",
    "username",
    "password",
)

# 旧版本只存储 use_ssl，读取时用于推导协议
_LEGACY_SSL_KEY = "notification.email.use_ssl"


def _config_key(name: str) -> str:
    return f"{KEY_PREFIX}{name}"


def _load_values() -> dict:
    keys = [_config_key(name) for name in _STORED_KEYS] + [_LEGACY_SSL_KEY]
    return {
        item.config_key: item.config_value
        for item in SystemConfig.objects.filter(config_key__in=keys)
    }


def _to_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if minimum <= value <= maximum else default


def _to_port(raw: str | None, protocol: str) -> int:
    default = 465 if protocol == PROTOCOL_SECURE_SMTP else DEFAULT_SETTINGS["port"]
    return _to_int(raw, default, 1, 65535)


def _resolve_protocol(stored: dict) -> str:
    protocol = stored.get(_config_key("protocol"), "")
    if protocol in PROTOCOLS:
        return protocol
    if _to_bool(stored.get(_LEGACY_SSL_KEY), False):
        return PROTOCOL_SECURE_SMTP
    return PROTOCOL_SMTP


def get_email_settings() -> dict:
    """读取界面展示用配置，密码仅以 hasPassword 标识。"""
    stored = _load_values()
    protocol = _resolve_protocol(stored)

    def raw(name: str, default: str = "") -> str:
        return stored.get(_config_key(name), default)

    use_tls = _to_bool(raw("use_tls"), False) and protocol == PROTOCOL_SMTP
    return {
        "name": raw("name"),
        "description": raw("description"),
        "fromEmail": raw("from_email"),
        "titlePrefix": raw("title_prefix", DEFAULT_TITLE_PREFIX),
        "protocol": protocol,
        "host": raw("host"),
        "port": _to_port(raw("port"), protocol),
        "timeout": _to_int(
            raw("timeout", str(DEFAULT_SETTINGS["timeout"])),
            DEFAULT_SETTINGS["timeout"],
            0,
            3600,
        ),
        "useTls": use_tls,
        "username": raw("username"),
        "hasPassword": bool(raw("password")),
        "configured": bool(raw("host")),
    }


def get_email_delivery_config() -> dict | None:
    """读取发送所需配置（含明文密码）；未配置服务器地址时返回 None。"""
    settings = get_email_settings()
    if not settings["host"]:
        return None
    stored = _load_values()
    password_token = stored.get(_config_key("password"), "")
    return {
        **settings,
        "useSsl": settings["protocol"] == PROTOCOL_SECURE_SMTP,
        "password": decrypt_secret(password_token) if password_token else "",
    }


def _validate_payload(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    from_email = str(payload.get("fromEmail") or "").strip()
    title_prefix = str(payload.get("titlePrefix") or "")
    protocol = str(payload.get("protocol") or PROTOCOL_SMTP).strip().lower()
    host = str(payload.get("host") or "").strip()
    username = str(payload.get("username") or "").strip()
    if not name:
        raise ValueError("请输入名称")
    if not from_email:
        raise ValueError("请输入发送邮箱")
    if "@" not in from_email:
        raise ValueError("发送邮箱格式不正确")
    if protocol not in PROTOCOLS:
        raise ValueError("协议仅支持 SMTP 或 SECURE_SMTP")
    if not host:
        raise ValueError("请输入 SMTP 主机")
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        raise ValueError("SMTP 端口必须是数字") from None
    if not 1 <= port <= 65535:
        raise ValueError("SMTP 端口范围应为 1 ~ 65535")
    try:
        timeout = int(payload.get("timeout"))
    except (TypeError, ValueError):
        raise ValueError("超时秒数必须是数字") from None
    if not 0 <= timeout <= 3600:
        raise ValueError("超时秒数范围应为 0 ~ 3600")
    return {
        "name": name,
        "description": description,
        "from_email": from_email,
        "title_prefix": title_prefix,
        "protocol": protocol,
        "host": host,
        "port": port,
        "timeout": timeout,
        # SECURE_SMTP 使用 SSL 直连，此时忽略 STARTTLS
        "use_tls": bool(payload.get("useTls")) and protocol == PROTOCOL_SMTP,
        "username": username,
    }


def save_email_settings(payload: dict) -> dict:
    """保存配置；密码留空表示保持原值。"""
    values = _validate_payload(payload)
    password = str(payload.get("password") or "")

    for name, value in values.items():
        stored_value = (
            ("true" if value else "false") if isinstance(value, bool) else str(value)
        )
        SystemConfig.objects.update_or_create(
            config_key=_config_key(name),
            defaults={
                "config_name": f"通知邮件服务器:{name}",
                "config_value": stored_value,
                "config_group": CONFIG_GROUP,
                "is_system": True,
            },
        )
    if password:
        SystemConfig.objects.update_or_create(
            config_key=_config_key("password"),
            defaults={
                "config_name": "通知邮件服务器:password",
                "config_value": encrypt_secret(password),
                "config_group": CONFIG_GROUP,
                "is_system": True,
            },
        )
    return get_email_settings()


def _build_connection(config: dict, password: str):
    from django.core.mail import get_connection

    return get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=password,
        use_tls=config["useTls"],
        use_ssl=config["useSsl"],
        timeout=config["timeout"] or None,
    )


def _validate_connection_payload(payload: dict) -> dict:
    protocol = str(payload.get("protocol") or PROTOCOL_SMTP).strip().lower()
    host = str(payload.get("host") or "").strip()
    if protocol not in PROTOCOLS:
        raise ValueError("协议仅支持 SMTP 或 SECURE_SMTP")
    if not host:
        raise ValueError("请输入 SMTP 主机")
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError):
        raise ValueError("SMTP 端口必须是数字") from None
    if not 1 <= port <= 65535:
        raise ValueError("SMTP 端口范围应为 1 ~ 65535")
    try:
        timeout = int(payload.get("timeout"))
    except (TypeError, ValueError):
        raise ValueError("超时秒数必须是数字") from None
    if not 0 <= timeout <= 3600:
        raise ValueError("超时秒数范围应为 0 ~ 3600")
    return {
        "host": host,
        "port": port,
        "timeout": timeout,
        "username": str(payload.get("username") or "").strip(),
        "useTls": bool(payload.get("useTls")) and protocol == PROTOCOL_SMTP,
        "useSsl": protocol == PROTOCOL_SECURE_SMTP,
    }


def check_email_connection(payload: dict) -> None:
    """使用表单值测试 SMTP 连接；密码留空时使用已保存的密码。"""
    config = _validate_connection_payload(payload)
    password = str(payload.get("password") or "")
    if not password:
        stored = _load_values()
        password_token = stored.get(_config_key("password"), "")
        password = decrypt_secret(password_token) if password_token else ""
    connection = _build_connection(config, password)
    try:
        connection.open()
    finally:
        connection.close()


def send_test_email(recipient: str) -> None:
    """使用已保存的配置发送一封测试邮件。"""
    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    config = get_email_delivery_config()
    if config is None:
        raise ValueError("请先配置 SMTP 服务器地址并保存")

    connection = _build_connection(config, config["password"])
    from_email = config["fromEmail"] or getattr(
        django_settings, "DEFAULT_FROM_EMAIL", None
    )
    send_mail(
        f"{config['titlePrefix']}DevOps 平台测试邮件",
        "这是一封来自 DevOps 平台「系统设置 - 通知设置」的测试邮件。",
        from_email,
        [recipient],
        connection=connection,
        fail_silently=False,
    )
