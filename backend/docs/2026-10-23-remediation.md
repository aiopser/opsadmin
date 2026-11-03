# 2026-10-23 全局审查修复与升级说明

本说明对应 [原始审查 R01–R12](2026-10-23-global-review.md) 与当前工作区的修复。实现状态、最终检查结果和证据边界统一见 [current-status.md](current-status.md)。本轮没有执行生产部署、真实主机/云调用、真实 MySQL 并发或浏览器验收。

## 修复的行为

用户管理拒绝写入 Django 特权字段和内部认证状态，关联角色的可授予权限与数据范围单独验证。定时、手工、任务单、克隆、重试和 Worker 执行收敛到统一授权入口，在运行时按当前活跃身份重新核验高危执行权限。

任务单及定时定义的秘密输入进入独立加密字段，接口返回脱敏值并支持保留原秘密。运行、节点、主机和日志的读取范围统一。登录失败策略真正参与锁定，改密/重置使旧认证版本失效；首次或重置密码用户先进入个人中心改密。

异步执行使用原 attempt/task 身份条件写入，旧结果、控制台和心跳不能覆盖新重试；仅由失败阻断的后继节点在重试时恢复，条件分支跳过保留。云同步终态与 Collector 写入受状态围栏保护，纳管回读另有 token/state 代次围栏。新建 Windows 资产使用正确连接默认值，已有手工连接配置保留。

前端脚本与 Git 请求校验完整身份，切换、重置和关闭使旧正文失效。流程保存使用独立提交载荷和提交时快照，保存中禁用编辑与重复提交，出现新变化则阻止发布。复杂模块默认参数按 JSON 序列化，脚本选择显示服务层 camelCase DTO，动态导航使用命名路由。

执行预览新增 `executionRequestId`；所有手动确认入口，包括历史弹窗/抽屉、任务单和定时立即运行，随目标与确认摘要透传原 ID。响应丢失后重试同次确认不应再创建运行；重新手动预览产生新 ID。请求记录按保留策略压缩响应后仍保留防重 tombstone，旧请求不能被重新执行。

Jenkins 取消只停止本平台等待，记录 `WAIT_CANCELED` 并提示远端构建可能继续。资源申请新增带证据、权限、二次校验和审计的人工核实结案，避免以改数据库或重新 apply 代替恢复；不能证明完整创建的申请继续保持待核实。

## 本轮新增迁移

| 迁移 | 内容 | 升级要求 |
| --- | --- | --- |
| `user.0002_security_session_policy` | 认证版本、必须改密标志、登录失败计数与锁定截止时间 | API/认证进程同版；校验旧 token 撤销与首次改密流程 |
| `jobs.0020_definition_secret_inputs` | 任务单/定时定义新增加密秘密字段，迁移历史秘密输入；定义版本缺失时保守保护全部输入值 | 数据迁移不可逆，必须备份数据库与原凭据加密密钥 |
| `jobs.0021_execution_request_key` | 执行请求 ID、操作者/路径唯一约束、载荷摘要与加密响应 | 全部创建入口同版，保留防重记录，不手工清空表来“解锁”请求 |
| `provisioning.0005_reconciliation_ownership` | attempt 新增回读认领 token | API 与所有专用 Worker 同版，防止旧投递继续无围栏提交 |
| `provisioning.0006_manual_resolution_evidence` | 人工核实预览的操作者、代次、摘要、过期、外部证据与结案记录 | UI/API/Worker 同版，按 review 权限与独立审核要求配置角色 |

本轮使用实际 `.py` 迁移文件，不把历史缓存文件当成迁移图。不得删除迁移、`--fake` 或重建生产迁移基线来绕过差异。

这里的增量升级假定目标环境已经采用仓库当前 V2 迁移基线。仍使用旧系统表或旧迁移历史的环境，必须先制定并演练单独的数据搬迁方案，不能直接应用 initial 或伪造迁移状态；参见 [迁移基线说明](migration-baseline.md)。

## 升级顺序

1. 冻结新任务、定时投递、定义编辑与资源写操作；停止 Beat，按维护方案排空或停用 Worker，确认没有新旧消费者混用同一队列。对未决外部执行先保留证据。
2. 备份数据库、已有 `CREDENTIAL_ENCRYPTION_KEY`、state 密钥环、私有运行日志、Terraform 制品和独立备份目录。记录旧版本、配置摘要与恢复位置；备份不能只包括数据库。
3. 在隔离 MySQL 副本演练完整迁移与恢复，验证旧定义秘密可解密且接口脱敏。本轮 SQLite/mock 回归不能替代此步骤。
4. 部署锁定依赖与同一版本的前端、API、ASGI、全部普通/专用 Worker 和 Beat；由部署进程执行迁移与种子同步。不要让旧 Worker 在新 schema/协议下继续运行。
5. 在维护环境检查认证、路由、队列、私有存储与加密配置，再按 API/ASGI、Worker、Beat 的顺序恢复服务。每个环境只运行一个有效 Beat 调度实例。
6. 使用专用测试用户与资产验证必改密码、秘密定义编辑、高危授权、同次确认重试、节点重试、云回收/回读以及人工核实权限。记录实际命令、版本、环境与结果后再开放入口。

在 `backend/`、已明确确认目标数据库及配置后执行：

```text
python -m poetry run python manage.py migrate --plan
python -m poetry run python manage.py migrate
python -m poetry run python manage.py init_system_settings
python -m poetry run python manage.py init_worker_pools
python -m poetry run python manage.py sync_scheduled_jobs
```

`init_system_settings --sync-menu-layout` 仅在确实需要同步内置菜单顺序时使用；普通初始化不应覆盖现有菜单展示选择。`init_worker_pools` 保留已有默认池配置，实际消费者队列仍以数据库池配置为准。

jobs.0020 的 `RunPython` 没有反向解密迁移。若升级失败，先停止新服务写入并保留失败证据，再按经过演练的数据库与密钥/制品恢复方案处理；只回滚代码不会恢复旧定义语义，换一把密钥也不能解密已迁移值。恢复操作细节见 [安全恢复 Runbook](security-and-recovery-runbook.md)。

## 实际服务入口示例

以下命令来自当前 `devops.wsgi`、`devops.asgi`、`devops.celery` 和 `CELERY_BEAT_SCHEDULER` 配置，均在 `backend/` 运行。它们是部署模板，不能替代目标机器上的托管、TLS、反向代理、权限与配置验收；本轮未启动这些真实服务。

```text
# Linux HTTP API；如采用 ASGI 同时提供 HTTP，可按部署架构合并此入口
python -m poetry run gunicorn devops.wsgi:application --bind 127.0.0.1:8000

# HTTP/WebSocket ASGI，反向代理需把 WebSocket 路径转发到此入口
python -m poetry run daphne -b 127.0.0.1 -p 8001 devops.asgi:application

# 普通任务与维护消费者：示例 devops.ansible 为 init_worker_pools 的新建默认值
# 现存 WorkerPool.queue_name 不同则调整队列，所有启用池均需有对应消费者
python -m poetry run celery -A devops worker -l INFO -Q task,ops,devops.ansible

# Terraform 专用受控 Linux Worker；固定 CLI/Provider 与私有存储
python -m poetry run celery -A devops worker -l INFO -Q provisioning -c 1

# 一个环境一个有效 Beat，使用项目定时调度器
python -m poetry run celery -A devops beat -l INFO --scheduler apps.jobs.scheduler:ScheduledJobScheduler
```

API、ASGI、普通 Worker、Terraform Worker 和 Beat 必须读取同一套密钥与业务配置。实时 Redis、Channel Layer 与日志/制品共享存储需要按拓扑配置；不能仅凭进程启动成功判断多实例可用。

## 验证与未验收项

专项回归入口包括前端 `test-review-frontend-races.cjs`、`test-auth-first-password.cjs`、`test-execution-request-id.cjs`、`test-module-default-args.cjs`，后端执行授权/代次、定义秘密、用户安全、云同步与人工核实测试。10 月 24 日最终联合回归为 1011 passed、6 skipped，另有 39 subtests passed；前端契约 67 passed。完整命令、检查边界与警告见 [当前状态](current-status.md)。

本轮没有完成真实 MySQL 迁移/并发、Redis 多实例故障、真实 Jenkins/主机/通知、固定 Provider 的真实云创建/IAM 拒绝测试、关键浏览器端到端、容量压测或生产恢复演练。历史隔离实验仍可查阅，不能自动升级为本轮通过。

上线前还需完成 [云 IAM 验证附件](cloud-iam-validation.md) 与 [资源申请专项部署验收](resource-provisioning-deployment.md)；缺失 state、部分创建或资源归属冲突的人工处理仍受 [安全恢复 Runbook](security-and-recovery-runbook.md) 限制。
