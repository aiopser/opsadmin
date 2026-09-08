# T11 输出归档

Runner 输出先脱敏，再通过 Django `job_logs` storage 保存不可变分块。默认每个运行上限 16 MiB，`DEVOPS_LOG_MAX_BYTES` 配置上限；下载每次读取最多 64 KiB。截断保持 UTF-8 字符和 ANSI 控制序列完整，响应 `X-Log-Truncated` 指示截断。

`GET /api/v1/{tasks|ops}/runs/{id}/log` 使用运行 owner 与 RBAC 权限，拒绝路径参数，返回附件，不公开存储路径。失败运行可以下载已经归档的输出。归档失败记录异常类型，不撤销已提交的事件；因此下载不是完整事件存储的替代品。

默认文件存储根目录由 `DEVOPS_LOG_ROOT` 指定。多 Worker/API 必须配置共同可访问的 `STORAGES['job_logs']`，或挂载共享目录；本地磁盘不自动共享。本次没有真实共享存储和多实例验证。

已删除 `ops/tasklog`、Celery 日志捕获信号及 `CELERY_LOG_DIR`。测试使用临时文件目录和 SQLite 测试库，不操作已有数据库。
