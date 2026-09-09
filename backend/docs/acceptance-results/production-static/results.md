# 第 5 节验收结果：生产配置静态检查

执行日期：2026-09-09
未启动生产服务、未执行生产迁移、未连接生产 Redis/MySQL/Worker、未访问生产主机。

## 实际命令

拒绝行为实测脚本：`backend/.pytest_cache/check_prod_settings.py`（临时，不入库），逐项注入/清空环境变量后 `django.setup()` 验证。

## 检查结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| `production_settings.py` 拒绝缺失强密钥 | PASS（实测） | 无环境变量时 `ImproperlyConfigured: Production requires a strong DEVOPS_SECRET_KEY` |
| 弱 SECRET_KEY 被拒绝 | PASS（实测） | `django-insecure-` 前缀即拒绝；长度 < 50 拒绝 |
| `DEVOPS_PRODUCTION_ALLOWED_HOSTS` 显式配置 | PASS（代码+实测） | 空/`*` 拒绝（production_settings.py:22-23）；实测中因检查顺序在 CREDENTIAL_KEY 之后，未单独触发，以代码为准 |
| `DEVOPS_CREDENTIAL_ENCRYPTION_KEY` 存在且合法 | PASS（实测） | 非法值 `ImproperlyConfigured`（Fernet 构造校验，隐含 32 字节密钥）；合法值加载成功 |
| 合法最小配置安全属性 | PASS（实测） | DEBUG=False、SECURE_SSL_REDIRECT=True、HSTS=31536000、SESSION/CSRF cookie secure=True |
| 前端无 fixture/mock/演示地址 | **修复 1 处** | `frontend/.env.prod` 原指向 `https://mock.apifox.cn/...` 与 `http://localhost:9529`，已改为 `https://api.example.com` 占位 + TODO(deploy) 注释；构建生产包前必须替换为实际生产地址 |
| 前端 API base / WS URL / Origin 白名单一致性 | 待部署核验 | 生产前端地址未定；后端 `DEVOPS_REALTIME_ALLOWED_ORIGINS` 与 `DEVOPS_PRODUCTION_ALLOWED_HOSTS`/CORS 由部署时注入，静态层面无硬编码不一致 |
| Redis/DB/队列/归档指向预期环境 | 设计核验 PASS | 生产 DB/Redis 经 `config/devops.ini` + `DEVOPS_REALTIME_REDIS_URL`/`DEVOPS_LOG_ROOT` 注入，无硬编码生产地址；deployment.md 明确独立 MySQL 新库/独立 Redis/共享归档要求 |
| 新旧 Worker 不同队列 | 设计核验 PASS | WorkerPool.queue_name 驱动（默认池 `devops.ansible`，`init_worker_pools.py`），Celery 默认任务队列 `task`；deployment.md 明确"不得让新旧 Worker 消费同一队列"，部署时按池核验 |
| 迁移目标为独立新库 | PASS | deployment.md 明确"不得对已有数据库运行本分支迁移"；本次空库 43 迁移全部成功（见 ../mysql/results.md）佐证迁移图自洽 |
| 生产配置无测试 token/静态密码 | PASS | `production_settings.py` 全文无密钥硬编码；`config/devops.ini` 为开发环境文件（开发库凭据），不用于生产 |

## 发现与处置

1. **`frontend/.env.prod` 含 mock/演示地址（已修复）**：原 `VITE_SERVICE_BASE_URL=https://mock.apifox.cn/m1/3109515-0-default`、`VITE_OTHER_SERVICE_BASE_URL` 含 `http://localhost:9529`。若直接构建生产包会指向 mock 服务。已替换为显式占位符并加 TODO 注释；生产构建前必须替换为真实地址。
2. ALLOWED_HOSTS 拒绝行为建议内网部署演练时实测一次（本次因检查顺序未单独触发，代码路径明确）。

## 回滚动作

- `.env.prod` 修改可通过 git revert 恢复；不影响任何运行时环境。
- 未访问生产资产，无其他回滚需求。
