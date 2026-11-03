# 资源交付 state 保护与运行保障实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有创建链路中加入可验证的独立备份、受控恢复、制品保留、执行租约和运行监控。

**Architecture:** 扩展现有 provisioning 应用，低层存储维持 `put(value) -> str`、`get(key) -> dict` 兼容接口，业务层新增制品索引和 state 版本。执行结果、纳管结果和保护状态分别保存；恢复仅切换已校验的控制状态并触发只读核实，不执行 apply。

**Tech Stack:** Django、Celery、Fernet、私有文件存储；Vue 3、Element Plus、UnoCSS。

**Spec:** `docs/superpowers/specs/2026-10-21-resource-delivery-evolution-design.md` 的第一阶段。

## Global Constraints

- 默认 15 秒更新心跳，90 秒未更新标记失联；已发出的 apply 不自动重试。
- 原始 plan 30 天、脱敏诊断 30 天、核实销毁后的历史 state/备份 180 天、业务摘要与审计至少 365 天。
- 活动资源最新 state、可恢复备份及待核实资源关键状态不按普通 TTL 删除。
- 备份失败不改写已知的创建结果；只读纳管继续，后续资源写操作被阻止。
- 不自动启用创建、不修改云 IAM、不迁移部署数据库、不删除现有制品；破坏性验证仅用隔离测试目录。
- 沿用当前会话直接实施方式，不自动提交，不改动无关工作区内容；前端编辑先读仓库技能，命令在 frontend/ 下使用 pnpm。
- 生产 Terraform 执行器限定 Linux 专用 Worker；Windows 开发环境通过 mock 验证进程协议，不模拟支持未经验证的进程树终止行为。

所有下文 Python 命令在 backend/ 的项目虚拟环境内执行。每阶段结束执行 `python manage.py check --settings=devops.test_full_settings`、`python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings`；完整回归命令为 `python -m pytest -q --basetemp=.pytest-provisioning`，均不连接部署数据库。

## Review Focus

- 加密 key 轮换后仍能读旧备份，缺少历史 key 时不能用新 key 冒充恢复成功。
- 仅有副本写入失败时不能清理工作目录，云创建成功不被通知或备份异常覆盖。
- Worker 主进程在线但执行子进程失联，要展示不同状态，并阻止旧租约回写成功。
- 恢复预览后账号、state 或任务状态改变，旧预览必须失效。
- 正在变成活动引用的制品不能与清理任务发生删除竞争。

## 文件与数据边界

新增模块：`state_crypto.py`（带版本密钥）、`state_protection.py`（state 索引与归档）、`state_restore.py`（恢复预览及确认）、`retention.py`（清理判定）、`worker_health.py`（心跳/租约/事件）。现有 `terraform.py` 继续负责进程与底层文件存储，`tasks.py` 只编排这些服务。

新增模型：

- `ProvisioningArtifact`：不可变存储键、main/backup、plan/state/diagnostic、所属申请/执行、摘要、字节数、key ID、持有标记、清理状态与到期时间；普通 API 不返回存储键。
- `ProvisioningStateVersion`：所属申请/执行、单调业务版本号、Terraform lineage/serial、内容摘要、主/备制品、保护状态 pending/protected/degraded/unverified、最近校验时间。
- `ProvisioningRestorePreview`：UUID、操作者、申请、候选 state 版本、内容/账号/当前控制版本摘要、15 分钟有效期、pending/consumed 状态。
- `ProvisioningWorker`：专用 Worker 标识、启动 epoch、实际消费队列、能力检查结果、最近心跳；不记录环境变量和密钥。
- `ProvisioningHealthIncident`：故障类别、对象指纹、open/resolved、脱敏摘要、通知快照。

申请增加 `active_state_version` 和 `state_generation`。计划和执行增加 `worker`、`execution_token`、`lease_expires_at`，执行另加 `apply_started_at`。不在本阶段新增 ResourceDeployment，后续可为 state 版本增加交付归属关联。

迁移用当前 `0003_provisioningrequest_notification_snapshot` 之后的 `0004_state_protection.py`、`0005_worker_health.py`；部署须先停止旧写入 Worker，禁止混用两代写入协议。迁移不读取文件、不伪造旧 state 元数据。

### Task 1：版本化加密、独立备份与 state 索引

**Files:** 新增 `backend/apps/provisioning/state_crypto.py`、`state_protection.py`、`test_state_protection.py`；修改 `models.py`、`terraform.py`、`backend/devops/settings.py`；生成 0004 迁移。

**Interfaces:** `StateKeyring.encrypt(value: dict) -> dict`、`decrypt(envelope: dict) -> dict`；`capture_state(attempt_id: int, files: dict[str, str]) -> ProvisioningStateVersion`；`check_protection_storage() -> None`。存储 envelope 为 schema=1、keyId、token；未知 schema/key 或认证失败明确拒绝。

- [ ] 写失败测试：主/备不同根、公开目录拒绝、空 key 配置拒绝、v1 加密后切换 v2 仍可读、缺 v1 时失败、损坏摘要失败、同一内容重复归档返回同一版本。
- [ ] 运行 `python -m pytest apps/provisioning/test_state_protection.py -q --basetemp=.pytest-provisioning`，确认是新增契约缺失导致失败。
- [ ] 实现配置 `PROVISIONING_STATE_KEYS`、`PROVISIONING_STATE_ACTIVE_KEY_ID`、`PROVISIONING_BACKUP_ROOT`，不自动生成生产密钥；主/备根不得相同、互相嵌套或位于 media/static。通过受控密钥环保存加密 envelope，限制明文制品 32 MiB、单份 state 16 MiB。
- [ ] 在私有根内临时写入、fsync、原子提交；捕获版本解析 state 的 lineage、serial、实例 ID，禁止把 raw attributes 返回页面。主副本和备份均验证成功才 protected；失败保存 degraded 及可恢复引用。
- [ ] 给现有旧格式制品保留只读兼容，不把旧引用标记为“已备份”。新增 `management/commands/provisioning_state_index.py`，默认 dry-run，显式执行时登记可校验旧引用；缺文件/密钥报告异常，不能覆盖主指针。
- [ ] 重跑 state 测试及 `test_runner.py`；隔离库执行 check、makemigrations --check，验证迁移无文件系统副作用。

### Task 2：接入 apply 归档与保护状态

**Files:** 修改 `tasks.py`、`services.py`、`reconciliation.py`、`serializers.py`、`test_worker_result.py`；新增 `test_protection_execution.py`。

**Interfaces:** 消费 Task 1 的 `capture_state`、`check_protection_storage`；`assert_write_protected(request_id: int) -> None`；详情返回 `stateProtection: {status, versionId, verifiedAt, message}`，不含私有键和路径。

新申请尚无 state 时执行存储/备份预检查，保护状态为 not_applicable，不能要求一个尚不存在的 protected state。已有 state 的申请则必须校验对应版本。

- [ ] 写失败测试：apply 成功但备份不可写时 execution_status=success、保护 degraded；只读纳管仍执行；后续写被拒；部分 state 被保留；没有合法 state 不能 protected；归档失败不清理唯一工作目录。
- [ ] 执行 `python -m pytest apps/provisioning/test_protection_execution.py -q --basetemp=.pytest-provisioning`，确认失败后接入。
- [ ] 在 plan 和 execute 前检查存储；在 apply 结果处理与归档之间明确分离异常边界。记录云侧已知结果，随后独立处理 state 保护、纳管、通知；不能让后两者改写前者。
- [ ] 仅在至少有可读取的持久状态引用后清理对应临时目录；备份异常保留修复入口，禁止自动重跑 apply。
- [ ] 给首次使用新协议的未执行旧计划返回“保护协议已升级，请重新生成计划”。`snapshot()` 纳入 state_generation；不静默改变已签名计划。
- [ ] 跑新增测试和现有 contracts/lifecycle/reconciliation/worker_result，确认重复投递仍只执行一次。

### Task 3：恢复预览与确认

**Files:** 新增 `state_restore.py`、`test_state_restore.py`；修改 `views.py`、`urls.py`、`serializers.py`、权限种子。

**Interfaces:** `preview_restore(request_id: int, actor, state_version_id: int) -> ProvisioningRestorePreview`；`confirm_restore(preview_id: UUID, actor) -> ProvisioningStateVersion`。API 为申请详情的 GET `state-versions`、POST `restore-preview`、POST `restore-confirm`，确认只接收 previewId 和预览摘要。

- [ ] 写失败测试：恢复另一个申请/账号的版本、错误 lineage、落后 serial、未知 key、跨操作者使用预览、过期预览、预览后控制版本变化、存在 queued/running/needs_reconciliation 写任务全部拒绝；确认不调用 TerraformRunner.apply。
- [ ] 运行 `python -m pytest apps/provisioning/test_state_restore.py -q --basetemp=.pytest-provisioning`，观察失败后实现。
- [ ] 预览从独立备份读取并校验，返回来源版本、时间、实例 ID、保护状态及阻止原因；不返回原始 state。申请行锁下确认摘要、配置版本、租约和最高已知 serial，单次消费预览。
- [ ] 恢复生成新的业务控制版本，保留原 lineage/serial，不伪造 Terraform serial；递增 state_generation，失效旧计划与审批，仅触发只读核实。更老备份不提供 force 入口，转人工接管报告。
- [ ] 为 `state_versions`、`restore_preview`、`restore_confirm` 分配独立权限，普通申请者不能凭详情权限恢复。写入事件和领域审计，测试原始 token 不出现在响应/审计中。
- [ ] 跑恢复及隔离回读测试，验证恢复后旧计划确实不能执行。

### Task 4：保留策略与可审计清理

**Files:** 新增 `retention.py`、`test_retention.py`、`management/commands/provisioning_artifact_gc.py`；修改制品索引与 state 保护服务。

**Interfaces:** `retention_candidates(now) -> QuerySet[ProvisioningArtifact]`；`purge_artifact(artifact_id: int, actor) -> bool`；命令默认 dry-run，只有 `--execute` 执行删除已登记候选。

- [ ] 写失败测试：30 天边界、持有标记、活动 plan、未知执行结果、恢复预览引用、活动 state/备份均不删除；清理报告生成后新增活动引用，执行阶段重新检查并保留；失败删除可重试但不重复记成功审计。
- [ ] 运行 `python -m pytest apps/provisioning/test_retention.py -q --basetemp=.pytest-provisioning`，确认失败。
- [ ] 实现 plan/diagnostic 30 天与摘要/审计至少 365 天的规则。本阶段所有 state 均无“云侧已销毁”的可信标记，因此不开放 state 删除；为未来 Lifecycle 可信销毁事件保留 180 天规则。
- [ ] 按登记键定位单一文件，验证解析路径留在对应私有根，拒绝符号链接；标记 deleting 后禁止新增活动引用，所有引用登记走同一行锁协议；不扫描 mtime 后递归清空目录。
- [ ] 报告未知孤立文件及其大小，留人工核实，不自动删除。验证所有破坏性测试只删除 pytest 自己创建的临时文件。

### Task 5：Worker 心跳、任务租约与故障事件

**Files:** 新增 `worker_health.py`、`test_worker_health.py`、`test_terraform_process.py`；修改 `apps.py`、`terraform.py`、`tasks.py`、`notifications.py`、`test_runner.py`、`backend/devops/settings.py`；生成 0005 迁移。

**Interfaces:** `record_worker_heartbeat(worker_id: str, epoch: str, queues: list[str], checks: dict) -> None`；`renew_lease(kind: str, object_id: int, token: UUID) -> bool`；`monitor_provisioning() -> dict`。`TerraformRunner.command(..., on_tick: Callable[[], bool] | None)` 每 15 秒续租，返回 False 时终止进程组并报告失联。

- [ ] 写失败测试：空闲 Worker 仍在线、普通 task 队列不能冒充 provisioning Worker、主进程在线但子任务租约过期、旧 epoch/token 不能回写、排队时间不算执行时间、超时后没有 apply 重投、故障和恢复通知分别只发一次。
- [ ] 运行 `python -m pytest apps/provisioning/test_worker_health.py apps/provisioning/test_terraform_process.py -q --basetemp=.pytest-provisioning`，确认失败。
- [ ] 在 Celery worker_ready/heartbeat_sent/shutdown 信号记录实际消费队列；心跳写入节流到 15 秒。进程执行改为 Popen 管理进程组，保留无 shell、参数数组、白名单环境及超时限制。
- [ ] plan/attempt 领取时生成 token；执行前及返回写入时检查 token 与当前状态。90 秒未续租的 apply 进入待核实，旧任务不能覆盖状态；保留旧无租约任务 45 分钟恢复兼容，不自动重新执行。
- [ ] Beat 每 30 秒检查 Worker、积压、租约和备份；排队超过 300 秒提示积压。事件 open/resolved 去重，通知沿用已有投递记录与重试机制，模板由受控部署设置配置，不新增直接发送工具调用。
- [ ] 增加脱敏 health DTO 和权限；健康状态只说明 Worker、依赖、存储及保护结果，不能把在线等同于“可保证创建成功”。

### Task 6：前端保护详情、运行状况与交付验收

**Files:** 新增 `frontend/src/views/task/provisioning/state-protection.vue`、`frontend/src/views/task/provisioning-operations/index.vue`；修改详情、provisioning API/类型、菜单权限种子、两种语言；新增 `backend/docs/provisioning-state-protection.md`。

**Interfaces:** 详情展示 Task 2 的 stateProtection；恢复消费 Task 3 两步接口；运行状况消费 GET `/api/v1/provisioning/operations/health`，页面路由由菜单注册。

- [ ] 页面编辑前读取 Vue、UI、TypeScript 技能。普通详情只显示保护摘要；授权管理员展开版本表和恢复预览。保留默认字体/颜色/表单风格，恢复确认明确写“恢复控制状态，不回滚云资源”。
- [ ] 运行状况展示 Worker、队列、异常任务、备份与保留规则；单独错误态和读取时间，不能用零代替读取失败。长名称截断有提示，表格状态有文字。
- [ ] 文档提供独立存储、密钥环、迁移停写、旧制品索引、主文件丢失演练、dry-run 清理及最小权限矩阵；云 RAM/CAM 操作权限以锁定 Provider 的实际调用和测试账号验证为准，不自动授予通配写权限。
- [ ] 前端目录运行 pnpm typecheck、范围 ESLint、pnpm build；后端运行新增测试、原 provisioning 回归及完整回归、check、makemigrations --check。保存实际结果。
- [ ] 测试环境实际演练丢主副本、备份不可写、Worker 中断及恢复；浏览器检查窄屏、空态、错误态和恢复流程。没有环境时明确列为待验收，不标完成、不运行真实资源变更。

## 后续边界

此计划交付第一阶段，不放开 update/delete，不创建 ResourceDeployment，也不新增私有云写入。云目录联动见同日独立计划；治理、生命周期及私有云继续按已确认设计另写可验收计划。
