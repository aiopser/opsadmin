"""内网多实例验收专用 settings（acceptance-intranet.md 第 2/3/4 节）。

隔离拓扑（相对 config/devops.ini 的开发环境）：
- MySQL：经 DEVOPS_MYSQL_NAME 环境变量指向全新空库（如 test_devops_acceptance）。
- Django cache：Redis db 5，KEY_PREFIX acceptance:django（开发环境用 db 0）。
- Celery broker/result：Redis db 7 / db 8（开发环境用 db 1 / db 2）。
- 实时通道：DEVOPS_REALTIME_REDIS_URL 指向 Redis db 6。
- 队列：验收 WorkerPool 使用专属队列名（如 acceptance.worker），不与 devops.ansible/task 共用。

仅用于隔离验收，禁止用于生产。
"""

import os

from .settings import *  # noqa: F403

assert os.environ.get("DEVOPS_ACCEPTANCE_MODE") == "yes", (
    "acceptance_settings requires explicit DEVOPS_ACCEPTANCE_MODE=yes opt-in"
)

_redis_host = ConfigDispose.get_redis("host")  # noqa: F405
_redis_port = ConfigDispose.get_redis("port")  # noqa: F405
_redis_password = ConfigDispose.get_redis("password")  # noqa: F405
_redis_auth = f":{_redis_password}@" if _redis_password else ""

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{_redis_auth}{_redis_host}:{_redis_port}/5",
        "TIMEOUT": 60 * 60 * 24,
        "OPTIONS": {
            "DECODE_RESPONSES": True,
            "PASSWORD": f"{_redis_password}",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.lzma.LzmaCompressor",
        },
        "KEY_PREFIX": "acceptance:django",
    }
}

CELERY_BROKER_URL = f"redis://{_redis_auth}{_redis_host}:{_redis_port}/7"
CELERY_RESULT_BACKEND = f"redis://{_redis_auth}{_redis_host}:{_redis_port}/8"
CELERY_TASK_DEFAULT_QUEUE = "acceptance.worker"
CELERY_TASK_ROUTES = {}
CELERY_BEAT_SCHEDULE = {}
