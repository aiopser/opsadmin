# 主机资源申请与交付实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现阿里云 ECS、腾讯云 CVM 的模板申请、变更计划、确认审批、执行和回读纳管闭环。

**Architecture:** 新增独立 provisioning Django 应用，避免把创建资源伪装成 Ansible 工作流。复用云账号身份、凭据加密、RBAC、通知渠道和 CMDB 资产规范化；交付使用独立 Terraform Worker 队列与私有加密制品。前端使用现有 Element Plus 组件，申请采用步骤条。

**Tech Stack:** Django、DRF、Celery、Terraform CLI；Vue 3、TypeScript、Element Plus、UnoCSS。

**Spec:** `docs/resource-provisioning-requirements.md`

## Global Constraints

- 首期仅创建主机；计划中包含删除、替换、修改已有资源即拒绝执行。
- 已发布模板不可原地修改；不接受普通申请者提交任意 HCL、执行命令或 Terraform 参数。
- 创建权限单独授权；默认需要他人审批。可由拥有策略管理权限的管理员明确配置无需审批。
- 同步凭据不自动获得创建权限；写凭据单独加密保存并绑定云账号。
- 不新增全局 UI 样式、字体或硬编码颜色；不硬编码前端路由。
- 不自动提交仓库、不部署、不调用真实创建 API，测试使用临时目录和替身执行器。

## Review Focus

- 云凭据轮换或账号禁用后，历史计划不能继续执行。
- apply 已发出但 Worker 失联时，不自动重试创建。
- 云 API 返回延迟或缺少私网 IP 时，保留待纳管状态，不创建不完整主机记录。
- 原始计划、状态、日志可能含敏感数据，不能使用公开 media 存储或直接序列化返回。
- 用户能看到申请不等于有权审批、执行或读取原始制品。

## 具体接口与状态约定

API 前缀 `/api/v1/provisioning`，保持项目不带结尾斜线约定。

- `templates`、`templates/{id}/versions`、`versions/{id}/publish`：维护并发布资源模板。
- `requests`、`requests/{id}`：申请及详情；列表默认仅申请者可见，管理权限可看全部。
- `requests/{id}/plan`：冻结版本、参数和账号，排队生成计划。
- `requests/{id}/confirm`、`approve`、`reject`：提交 planId 与 digest，服务端验证当前版本和权限。
- `requests/{id}/execute`：提交 planId、digest 与幂等键；仅执行该已确认保存计划。
- `requests/{id}/reconcile`：只重新核实云资源与纳管，不执行 apply。
- `requests/{id}/events`：分页返回脱敏事件，不提供原始 state 下载。

计划有效期默认 30 分钟；模板参数限制首期每次 1–20 台，只允许既有 VPC、子网、安全组。服务端策略可进一步降低配额。数量不是价格，首期无价格接口时明确显示“费用以云平台账单为准”，不得展示虚假估价。

申请、计划、审批、执行、纳管分别保存状态；每次生成新计划递增 revision，旧审批失效。凭据版本变化使旧计划失效。审批默认禁止本人审批；审批通过不自动创建，申请者仍需点击执行。

### Task 1：独立数据模型与申请权限

**Files:** 新建 `backend/apps/provisioning/{apps,models,serializers,views,urls,permissions}.py`、`migrations/`、`test_requests.py`；修改 `backend/devops/urls.py`、实际项目 settings 应用列表、`backend/apps/permission/seeds/{menus,permissions}.py`。

**Interfaces:** `ResourceTemplate`、`ResourceTemplateVersion`、`ProvisioningCredential`、`ProvisioningRequest`、`ProvisioningPlan`、`ProvisioningApproval`、`ProvisioningAttempt`、`ProvisioningEvent`。所有历史实体使用 PROTECT 或冻结快照；凭据仅返回已配置标识。资源 ID 与 CMDB 资产关联保存在 Attempt 中。

- [ ] 写失败测试：普通用户不能读取他人申请；无权限不能发布、审批、执行；发布版本不能修改；私有云账号暂不支持申请；写凭据绑定账号且不回显。
- [ ] 运行 `.venv/Scripts/python.exe -m pytest apps/provisioning/test_requests.py -q`，确认断言失败后实现模型、迁移、CRUD 与权限种子。
- [ ] 运行上述测试、Django check、makemigrations --check；从空测试库验证迁移。

### Task 2：受控模板与计划生成

**Files:** 新建 `backend/apps/provisioning/{templates,validation,artifacts,terraform,tasks}.py`、`test_plans.py`；模板放 `backend/apps/provisioning/templates/terraform/{aliyun,tencent}/`。

**Interfaces:** `build_plan(request_id: int) -> None`；`TerraformRunner.plan(workspace, timeout_seconds)` 返回退出码、计划文件与 JSON 计划；`ArtifactStore.put/get` 仅接收服务端生成的键。digest 覆盖保存计划字节、模板内容摘要、规范化参数、账号、凭据版本及 CLI/provider 锁文件摘要。

- [ ] 写失败测试：参数超限、地域不在账号范围、跨账号网络、删除/替换/修改动作、无变更、输出非 JSON、命令超时和缺少 CLI 均产生可定位错误；错误无密钥。
- [ ] 实现服务端参数白名单；云 API 校验网络归属。模板仅创建实例及附属磁盘，不创建网络与安全组、不配置公网开放规则。
- [ ] 实现独立目录与参数数组 subprocess，禁止 shell=True。CLI 路径和 provider 版本由部署配置与锁文件固定，不按用户输入下载安装。
- [ ] 原始 plan/state 加密写到私有目录，文件权限最小化；前端仅得到脱敏资源变更摘要。生产未配置私有存储、固定执行器或凭据时明确拒绝生成计划。
- [ ] 运行计划测试，确认生成失败不进入可确认状态；日志脱敏、制品访问隔离和超时清理通过。

### Task 3：确认、审批和执行并发约束

**Files:** 新建 `backend/apps/provisioning/{policy,services}.py`、`test_approval.py`、`test_execution.py`；扩展 views/tasks。

**Interfaces:** `confirm_plan(request_id, actor, plan_id, digest)`、`approve_plan(...)`、`execute_plan(request_id, actor, plan_id, digest, idempotency_key)`。内部用 transaction.atomic/select_for_update，任务在 on_commit 后入队。

- [ ] 写失败测试：审批前执行、本人审批、越权切换账号、过期计划、修改参数、轮换凭据、账号禁用、重复确认和重复任务投递。
- [ ] 实现服务端审批策略和 revision 校验；每次执行重新检查权限、账号、模板有效性、计划摘要和状态。
- [ ] 实现申请独立持久 state 与锁；保存计划只允许一个执行 Attempt。Worker 在 apply 发出前持久化状态，丢失租约后进入结果待核实，禁止自动重投 apply。
- [ ] 运行测试，验证双并发 execute 只调用一次执行器，修改任意冻结输入后旧审批失效。

### Task 4：云回读、幂等纳管与异常恢复

**Files:** 新建 `backend/apps/provisioning/{reconciliation,providers}.py`、`test_reconciliation.py`；复用 `backend/apps/cmdb/sync_inventory.py`。

**Interfaces:** `reconcile_attempt(attempt_id: int) -> None`；云适配器按已记录 instance IDs 回读，不使用整账号同步结果推断申请资源。

- [ ] 写失败测试：部分实例已创建、超时后存在实例、apply 返回非零但有 state、云 API 暂不可见、实例无私网 IP、重复纳管与跨账号相同 IP。
- [ ] 从受控输出与 state 收集实例 ID；资源身份不确定时保留待人工核实，不重新创建。对已知 ID 的回读按 10/30/60/120/300 秒有界重试。
- [ ] 复用账号+source_id 唯一身份和 cloud_inventory_values，保留人工字段；只有有效资产字段才纳管。重新核实只执行回读和 upsert。
- [ ] 运行测试，验证重新纳管不调用 Terraform apply，不删除现有资产，不回滚部分成功资源。

### Task 5：前端模板、申请步骤条与详情

**Files:** 新建 `frontend/src/service/api/provisioning.ts`、`frontend/src/typings/api/provisioning.d.ts`、`frontend/src/views/task/provisioning/{index.vue,request-drawer.vue,detail.vue}`、`frontend/src/views/automation/resources/provisioning/index.vue`；修改后端菜单种子和现有主机资产页申请入口。

**Interfaces:** 使用上述 API；后端返回 allowedActions 控制按钮可用性，前端隐藏不是权限校验。列表分页，详情分别显示计划、审批、执行和纳管状态。

- [ ] 编辑前读取仓库 Vue、UI、TypeScript 技能；复用搜索栏、抽屉、步骤条、表格、确认弹窗与日志组件。
- [ ] 完成“模板与账号 → 参数 → 变更计划 → 确认或审批 → 交付结果”；选项由后端能力接口返回，不允许自由填写 Terraform 内容。
- [ ] 精确展示将创建的每台实例、数量、账号与地域；审批等待、过期、结果待核实、已创建未纳管都有明确文案与动作。
- [ ] 页面测试覆盖切换模板重置不兼容字段、重复点击、审批失效、返回继续查看、分页、空数据与长主机名。
- [ ] 在 frontend 运行 pnpm typecheck、相关测试、pnpm exec eslint . --quiet、pnpm build；运行页面后做真实浏览器视觉验收，不能以构建成功代替截图核对。

### Task 6：审计、通知和部署验收

**Files:** 新建 `backend/apps/provisioning/{audit,notifications}.py`、`test_notifications.py`、`backend/docs/resource-provisioning-deployment.md`；扩展现有通知变量目录与预览。

- [ ] 写失败测试：待审批、审批拒绝、执行失败及纳管失败通知幂等；制品与密钥不进入审计和消息。
- [ ] 复用 NotificationRecord 投递机制，增加 provisioning 场景变量目录、示例值与预览；审批和执行事件关联申请及计划 ID。
- [ ] 文档说明 Linux 专用 Worker、CLI/provider 锁定、私有加密 state、权限、备份、制品保留与恢复；生产默认关闭创建功能，配置完整后由管理员启用。
- [ ] 跑全后端回归和前端检查；人工验收模拟断网、Worker 中断、部分成功及纳管重试。真实付费云创建另由用户指定测试账号与资源额度后验收。

## 交付口径

逐项勾选并记录实际测试结果；未连接真实云时明确写“模拟链路已验证，真实云待验收”。缺少执行环境不能把创建申请标记为成功，不用空实现或演示数据冒充已交付能力。
