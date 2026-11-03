# DevOps 自动化与资产平台

本仓库包含 Vue 3 管理前端与 Django 后端，覆盖 CMDB、自动化资源、任务执行、定时任务、通知及 Terraform 资源申请。前端基于 Soybean Admin 的 Element Plus 变体 `@sa/elp`。

当前代码与验证状态以 [当前状态与文档索引](backend/docs/current-status.md) 为准。历史验收报告对应当时的代码和环境，不能直接作为当前版本的生产验收结论。

## 目录与服务职责

| 目录 / 服务 | 职责 |
| --- | --- |
| `frontend/` | Vue 3、TypeScript、Vite、Element Plus、UnoCSS、Pinia；pnpm workspace，公共子包位于 `packages/` |
| `backend/apps/user`、`permission`、`audit_center` | 用户、角色、菜单、API 授权、数据范围与审计 |
| `backend/apps/cmdb` | 主机、凭据引用、云账号与同步、资产探测 |
| `backend/apps/automation` | 脚本、Playbook、模块、API、Jenkins、Git 与通知资源及版本 |
| `backend/apps/jobs` | 流程、任务单、定时任务、运行与节点、事件、日志、Worker 池 |
| `backend/apps/provisioning` | 资源模板、审批、Terraform 计划/执行、state 保护、回读与人工核实 |
| `backend/apps/wiki` | 知识文档 |
| MySQL / Redis / Celery | 持久状态、缓存与实时通道、队列投递和异步执行 |
| API / ASGI / Beat / Worker | HTTP 接口、WebSocket、定时投递、执行与维护任务；必须使用同一发布版本 |

普通任务与 Terraform 交付使用独立执行环境。Terraform Worker 消费 `provisioning` 队列；普通 Worker 的队列应匹配数据库 `WorkerPool.queue_name`，并覆盖流程/维护使用的 `task` 与作业调度使用的 `ops` 队列。

## 功能边界

| 能力 | 当前实现 | 尚需按部署环境验证 |
| --- | --- | --- |
| 身份与授权 | 角色/API/菜单/数据范围、特权字段与授权边界、登录锁定、改密会话撤销、首次/重置密码引导 | 实际角色矩阵、缓存和多实例会话行为 |
| 自动化执行 | 脚本/Playbook/模块、不可变资源版本、流程、任务单、定时、预览确认、请求幂等、节点重试与日志 | 真实 Linux/Windows 主机、网关、Worker 故障与 MySQL 并发 |
| CMDB | 云同步、查询、同步回收与终态围栏、连接默认值 | 指定云账号权限、限流与真实资产兼容 |
| 资源申请 | 审批、受控 Terraform 执行、加密 state 与备份、纳管回读、带证据人工核实结案 | 固定 CLI/Provider、真实云创建、IAM 拒绝测试和恢复演练 |
| 通知与运行状态 | 通知模板、历史、重试、运行失败通知、健康与交付监控 | 真实收件端、共享存储与消息故障恢复 |

人工核实结案只接受能够证明已完整创建且可安全纳管的结果；缺失 state、部分创建或归属冲突仍保持待核实。取消 Jenkins 节点停止本平台等待，已触发的远端构建可能继续运行。

## 本地开发

前端要求 Node.js `>=20.19.0`、pnpm `>=8.7.0`；后端依赖以 `backend/pyproject.toml` 与 `poetry.lock` 为准，当前使用 Django 5.2 系列。真实 Ansible/Terraform Worker 使用受控 Linux 环境。

前端命令全部在 `frontend/` 执行，不使用 npm/yarn：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

按开发环境配置前端 `.env.test` / `.env.prod` 的 API 地址。前端动态路由由后端菜单生成，组件内使用命名路由。

后端使用独立开发配置、数据库、Redis、队列和私有制品目录。`devops.settings` 会读取环境变量及 `config/devops.ini`；先确认配置归属，再运行需要连接服务的命令。凭据加密密钥不能由每个进程各自生成。

```powershell
cd backend
python -m poetry install --no-root
python -m poetry run python manage.py check --settings=devops.test_full_settings
python -m poetry run pytest --ds=devops.test_full_settings
```

上述检查使用隔离测试设置。配置好独立开发服务后，可用 `python -m poetry run python manage.py runserver 127.0.0.1:8000` 启动 HTTP 开发服务；需要 WebSocket 时使用 `python -m poetry run daphne -b 127.0.0.1 -p 8000 devops.asgi:application`。

部署初始化、API/ASGI/Worker/Beat 启动示例和本轮不可逆迁移说明见 [当前版本升级说明](backend/docs/2026-10-23-remediation.md)。这些是操作指引，本轮没有执行生产部署或真实云/主机调用。

## 验证与贡献

在 `frontend/` 执行 `pnpm typecheck`、`pnpm lint`、`pnpm test:contracts`；lint 不改写文件，聚合回归自动发现 `frontend/scripts/test-*.cjs`。后端测试默认使用隔离设置，不能用 SQLite 或 mock 结果替代真实 MySQL、Redis、Runner 和云账号验收。

变更前阅读 [AGENTS.md](AGENTS.md)、对应项目技能及 [贡献约定](CONTRIBUTING.md)。后端质量检查与 CI 入口见 [开发质量门槛](backend/docs/development-quality.md)。

## 文档入口

- [当前状态与证据索引](backend/docs/current-status.md)
- [2026-10-23 修复与升级说明](backend/docs/2026-10-23-remediation.md)
- [安全与故障恢复 Runbook](backend/docs/security-and-recovery-runbook.md)
- [云 IAM 验证附件](backend/docs/cloud-iam-validation.md)
- [资源申请部署与专项验收](backend/docs/resource-provisioning-deployment.md)
- [原始全局审查 R01–R12](backend/docs/2026-10-23-global-review.md)
