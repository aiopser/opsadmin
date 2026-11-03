"""Runtime policy values shared by API entry points (no process-local cache)."""

from rest_framework.exceptions import ValidationError


def config_value(key, default=None):
    from apps.permission.models import SystemConfig

    value = (
        SystemConfig.objects.filter(config_key=key)
        .values_list("config_value", flat=True)
        .first()
    )
    return default if value is None else value


def positive_config(key, default):
    try:
        value = int(config_value(key, default))
        if value <= 0:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ValidationError(f"配置 {key} 必须是正整数，请联系管理员修正") from None


def validate_password_policy(password):
    minimum = positive_config("security.password.min_length", 6)
    if len(password) < minimum:
        raise ValidationError({"password": f"密码长度不能少于 {minimum} 位"})


def validate_upload(upload):
    from pathlib import Path

    maximum = positive_config("file.upload.max_size_mb", 20)
    if upload.size > maximum * 1024 * 1024:
        raise ValidationError(f"单个文件大小不能超过 {maximum} MB")
    configured = config_value("file.upload.allowed_extensions")
    if configured is None:
        return
    allowed = {
        part.strip().lower().lstrip(".")
        for part in str(configured).split(",")
        if part.strip()
    }
    extension = Path(upload.name).suffix.lower().lstrip(".")
    if not extension or extension not in allowed:
        raise ValidationError("不允许上传此文件类型")
