# 内网验收执行计划（外网未完成项）

本计划覆盖当前外网环境因资产不可达而未完成的验收项。内网 Agent 按以下方式执行并回传证据。所有项目均在隔离环境完成，禁止触碰生产资产（第 5 节仅允许静态检查）。

结果与产物建议归档至 `backend/docs/acceptance-results/`（`mysql/`、`multi-instance/`、`runner/`、`performance/`）。

## 1. MySQL 真实迁移、并发序列、锁和幂等

目标：确认新迁移图能在独立空 MySQL 上完整执行，并验证并发事件写入。

执行前提：

- 使用全新、临时、隔离的 MySQL 实例。
- 不使用已有 `django_migrations` 的旧库。
- 不使用 `--fake`。
- 设置专用端口，不能使用生产默认 3306。
- 配置：

```powershell
$env:DEVOPS_TEST_MYSQL_ISOLATED = "yes"
$env:DEVOPS_TEST_MYSQL_PORT = "<隔离端口>"
$env:DEVOPS_TEST_MYSQL_USER = "<隔离用户>"
$env:DEVOPS_TEST_MYSQL_PASSWORD = "<隔离密码>"
```

建议命令：

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate --settings=devops.test_mysql_settings
.\.venv\Scripts\python.exe manage.py check --settings=devops.test_mysql_settings
.\.venv\Scripts\python.exe -m pytest `
  apps/jobs/test_event_api.py `
  apps/jobs/test_event_delivery.py `
  apps/jobs/test_execution_entrypoints.py `
  --ds=devops.test_mysql_settings `
  --basetemp=.pytest_cache/mysql-acceptance `
  -q
```

需要额外确认：

- 两个或多个并发 producer 对同一个 run 写事件时，`sequence` 连续且不重复。
- 相同 `event_key` 重复提交只产生一个事件。
- 不同 node/attempt 的相同事件 key 不互相冲突。
- MySQL 1205/1213 锁冲突按设计重试，超过上限会明确失败。
- 记录数据库版本、隔离级别、并发数、锁等待和完整测试输出。

## 2. 多实例 API/ASGI、Worker、共享归档

目标：验证两个 API/ASGI 实例、两个 Worker 同时运行时，事件、队列和日志不会重复或丢失。

部署一个完全隔离的测试拓扑：

- API/ASGI：2 个实例。
- Worker：2 个实例。
- Redis：独立实例或独立 namespace。
- MySQL：独立数据库。
- `DEVOPS_LOG_ROOT` 使用两个实例都能访问的共享目录或共享存储。
- 两个 Worker 使用同一个测试 WorkerPool queue，但不能与旧系统共用队列。
- 两个 API/ASGI 使用相同的实时 Redis 配置和密钥。

验收场景：

1. 创建一个多节点运行，确认只生成一套运行记录。
2. 两个 Worker 同时竞争同一节点，确认只有一个 attempt 被领取。
3. 两个 ASGI 实例分别建立订阅，确认两个订阅者都能按 sequence 收到通知。
4. 事件通知重复投递，确认 REST 补拉后前端只保留一份。
5. 多个 Worker 同时写 stdout，确认日志归档不互相覆盖。
6. 从任意 API 实例下载日志，确认内容一致且权限正确。
7. 停止其中一个 API 或 Worker，确认运行最终状态仍能落库。

需要提供：

- 实例拓扑和队列名。
- Redis namespace、数据库名、归档路径。
- 每个场景的运行 ID、事件总数、重复数、丢失数、最终状态和日志校验值。

## 3. 真实隔离 Runner、灰度和恢复演练

目标：只在明确授权的隔离资产上验证 Linux Runner 成功、失败、取消及恢复。

隔离要求：

- 仅使用测试 Worker/主机，不使用生产主机、生产凭据、生产网关或生产队列。
- 测试目标地址、凭据引用和归档目录必须与生产隔离。
- 禁止通过默认配置自动发现资产。

场景：

1. Linux SSH 成功执行。
2. 命令失败，确认失败原因和退出码落库，且秘密不进日志。
3. 运行中发起取消，区分 `cancel_requested` 和 Worker 已确认 `canceled`。
4. Worker 在执行中终止，恢复任务扫描后记录失联结果，不自动重复执行具有外部副作用的命令。
5. Redis 短暂中断，REST 事件读取仍能完成。
6. 浏览器断开后重新打开详情，按 cursor 补齐所有事件。
7. 灰度只切换测试用户或测试权限组，确认新旧 Worker 不消费同一队列。

需要提供：

- 隔离资产清单和授权范围。
- 每个场景的 run ID、节点状态变化、事件序列、最终状态。
- Worker 终止时间、恢复扫描时间和是否发生重复执行。
- 灰度用户、队列、配置版本和回退记录。

## 4. 性能压测

目标：按计划验证首轮负载，不把结果当作生产容量承诺。

负载：

- 10 个运行。
- 20 个订阅者。
- 总计 100 events/s。
- 持续 10 分钟。
- 同时记录事件完整性、内存、P95 延迟和数据库锁等待。

压测前必须记录：

- API/ASGI/Worker/Redis/MySQL 版本。
- CPU、内存、磁盘和网络配置。
- Worker 数量、连接池、Redis 配置和数据库连接数。
- 归档存储类型及吞吐。

验收指标：

- 发送事件数 = 持久化事件数 = 消费者收到的唯一 sequence 数。
- 没有重复 sequence 或缺失 sequence。
- 记录通知到 REST 补拉完成的 P95 延迟。
- 记录 API、ASGI、Worker、Redis、MySQL 各自的峰值和结束内存。
- 记录 MySQL 锁等待、死锁和重试次数。
- 若内存持续增长或事件不完整，压测失败，不给容量结论。

建议将压测脚本和原始结果放在内网工作区，例如：

```text
backend/docs/acceptance-results/
  mysql/
  multi-instance/
  runner/
  performance/
```

## 5. 生产配置启动和生产资产连接

这一项不能直接作为普通验收执行。生产启动或连接生产资产必须有明确的发布授权、资产范围、时间窗口和回滚负责人。

在没有这些授权前，内网 Agent 只能做"生产配置静态检查"，不能启动生产服务、执行生产迁移、连接生产 Redis/MySQL、连接生产 Worker 或访问生产主机。

安全的静态检查包括：

- `production_settings.py` 是否拒绝缺失强密钥。
- `DEVOPS_PRODUCTION_ALLOWED_HOSTS` 是否显式配置。
- `DEVOPS_CREDENTIAL_ENCRYPTION_KEY` 是否存在且长度符合要求。
- Redis、数据库、队列、归档目录是否指向预期环境。
- 新旧 Worker 是否使用不同队列。
- 迁移目标是否为独立新库。
- 前端 API base URL、WS URL、Origin 白名单是否一致。
- 生产配置中没有 fixture 地址、测试 token、静态密码或演示请求头。

若明确授权生产窗口，仍应先做只读核验，再由负责人确认后执行启动和连接；不要让 Agent 自行决定连接生产资产。

## 回传要求

最终请内网 Agent 回传每项的：

- 实际命令；
- 环境和拓扑；
- 测试数量与结果；
- run ID/sequence/日志校验值；
- 跳过项及原因；
- 失败时的回滚动作；
- 是否访问过生产资产。
