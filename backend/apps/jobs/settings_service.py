"""作业执行默认参数，基于 SystemConfig 键值存储。"""

from apps.permission.models import SystemConfig

CONFIG_GROUP = "basic"

ENGINE_DEFAULTS = {
    "timeout": "300",
    "forks": "10",
    "host_strategy": "parallel",
    "serial_batch": "5",
    "max_fail_percentage": "0",
}

ENGINE_INT_KEYS = ("timeout", "forks", "serial_batch", "max_fail_percentage")


def _engine_key(key):
    return f"ops_engine_{key}"


def _load_values(prefix_fn, defaults):
    stored = {
        config.config_key: config.config_value
        for config in SystemConfig.objects.filter(
            config_key__in=[prefix_fn(key) for key in defaults]
        )
    }
    return {
        key: stored.get(prefix_fn(key), default) for key, default in defaults.items()
    }


def _save_values(prefix_fn, values):
    for key, value in values.items():
        SystemConfig.objects.update_or_create(
            config_key=prefix_fn(key),
            defaults={
                "config_name": f"ops:{key}",
                "config_value": str(value),
                "config_group": CONFIG_GROUP,
                "is_system": True,
            },
        )


def get_engine_settings() -> dict:
    values = _load_values(_engine_key, ENGINE_DEFAULTS)
    for key in ENGINE_INT_KEYS:
        try:
            values[key] = int(values[key])
        except (TypeError, ValueError):
            values[key] = int(ENGINE_DEFAULTS[key])
    return values


def _validate_engine_settings(values):
    if "host_strategy" in values and values["host_strategy"] not in {
        "parallel",
        "serial",
        "rolling",
    }:
        raise ValueError("host_strategy must be parallel, serial or rolling")
    for key in ("timeout", "forks", "serial_batch"):
        if key in values and int(values[key]) <= 0:
            raise ValueError(f"{key} must be greater than 0")
    if (
        "max_fail_percentage" in values
        and not 0 <= int(values["max_fail_percentage"]) <= 100
    ):
        raise ValueError("max_fail_percentage must be between 0 and 100")


def save_engine_settings(payload: dict):
    values = {key: payload[key] for key in ENGINE_DEFAULTS if key in payload}
    _validate_engine_settings(values)
    _save_values(_engine_key, values)
    return get_engine_settings()
