# 云资源目录与申请联动实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 阿里云 ECS、腾讯云 CVM 的申请和模板配置通过只读云 API 选择资源，展示名称、规格及真实可用性。

**Architecture:** 在 provisioning 内新增 catalog 服务及两个厂商适配器，SDK 查询结果先规范化，再与模板策略取交集。申请目录和管理员配置目录分路由授权；前端共用目录选择组件，历史计划继续保留冻结参数。

**Tech Stack:** Django/DRF、Django cache、现有 ECS/CVM SDK 与补充 VPC SDK；Vue 3、Element Plus。

**Spec:** `docs/superpowers/specs/2026-10-21-resource-delivery-evolution-design.md` 的第二阶段。

## Global Constraints

- 仅只读查询，使用云账号读取凭据；不使用创建密钥扩大可见范围。
- 普通目录缓存 120 秒、可用性 30 秒，每次命中前仍做授权校验。
- 精确剩余数量只有接口明确返回且单位一致时才显示；缺失显示未知，不能造 0 或充足。
- 查询必须分页，有剩余页时不能把第一页说成完整清单；旧静态模板保持兼容，新发现规则必须发布新版本。
- 新版必要资源无法验证时拒绝计划，不退回任意输入 ID；失效/售罄选项禁选且有原因。
- 不自动升级生产密钥权限、不调用创建 API；依赖必须进入 pyproject 与 poetry.lock，不依赖开发机偶然安装。
- 前端遵守仓库 Vue、UI、TypeScript 技能，Element Plus、默认字体、统一搜索/表单与动态路由。
- 按用户优先级，在 state 保护计划完成代码集成后执行本计划；两计划分离的是功能与验收，不表示要并行修改同一申请链路。

Python 命令在 backend/ 项目虚拟环境执行；阶段检查为 `python manage.py check --settings=devops.test_full_settings`、`python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings`；完整后端回归为 `python -m pytest -q --basetemp=.pytest-provisioning`。

## Review Focus

- 同一缓存项在用户被撤权后不能继续返回数据。
- 可见规格不等于有库存，库存状态不等于精确剩余台数。
- 策略过滤掉整页云资源时，分页必须能继续而不是报“没有资源”。
- 请求账号切换后旧响应晚到，不能覆盖新账号选择。
- 管理员配置目录权限不能通过修改普通请求的 mode 字段获得。

## 统一契约

新增 `backend/apps/provisioning/catalog/`，分为 types、policy、service、aliyun、tencent。DTO 与 vendor 原始对象隔离，不直接返回 SDK response。

- `CatalogQuery`：version_id、credential_id/source_id、region、kind、search、zone_id、image_id、instance_type、vpc_id、subnet_id、cursor、limit。
- kind 枚举：zones、images、instance_types、vpcs、subnets、security_groups、quota、availability。
- `CatalogItem`：id、name、description、available（true/false/null）、unavailableReason、attributes。属性仅允许 cpuCores、memoryMiB、architecture、osFamily、cidr、zoneId、vpcId、availableIpCount、quotaLimit、quotaUsed、quotaRemaining、unit 等已声明字段，不带凭据、原始响应或任意标签。
- `CatalogPage`：items、hasMore、nextCursor、observedAt、warnings；默认 50、最大 100 条。每次最多扫描 5 个厂商页，策略过滤导致空页时仍返回正确 hasMore 和下一游标。
- 错误：category、operation、message、suggestion、requestId；响应不暴露 Secret、签名 URL 或堆栈。

API 为 GET `/api/v1/provisioning/catalog`（已发布模板申请目录）及 GET `/api/v1/provisioning/catalog/configuration`（资源管理员配置目录）。运行模式由路由决定，拒绝客户端自行设置 mode。

### Task 1：目录契约、授权、缓存与策略

**Files:** 新增 `catalog/__init__.py`、`types.py`、`policy.py`、`service.py`、`catalog_views.py`、`test_catalog_contract.py`；修改 urls、权限种子、版本 serializer。

**Interfaces:** `query_catalog(actor, query: CatalogQuery, *, configuration: bool = False) -> CatalogPage`；`filter_catalog_items(items: list[CatalogItem], policy: dict) -> list[CatalogItem]`。服务函数内部模式只供视图显式调用，不由 query 覆盖。

- [ ] 写失败测试：非法 kind、缺失依赖、禁用账号、跨账号凭据、未发布模板、被撤销的 credential.use、越过模板范围、伪造管理员 mode、伪造游标、缓存撤权均被拒绝。
- [ ] 运行 `python -m pytest apps/provisioning/test_catalog_contract.py -q --basetemp=.pytest-provisioning`，确认缺少新接口而失败。
- [ ] 申请查询校验模板/凭据/账号关联、地域和 credential.use；管理员配置查询另需 catalog.configure、版本维护及目标账号查看权限，不通过该接口默认授予创建权限。
- [ ] 实现带签名的 10 分钟游标，绑定操作者、账号配置版本、模板策略摘要、筛选条件及 provider 下一页；改变任何一项后拒绝旧游标。
- [ ] 缓存包含同样的权限范围/配置/策略维度与 TTL，缓存前后均不记录明文凭据；查询错误不缓存为成功空页。
- [ ] 模板 constraints 扩展为有 schemaVersion 的受控 selectors：账号/地域、网络与安全组标签、镜像来源/系统/名称前缀、CPU/内存范围/规格系列。保留旧 allowlist 兼容，不接受脚本、任意 SDK 参数或正则表达式。

### Task 2：厂商只读目录适配器及诊断

**Files:** 新增 `catalog/aliyun.py`、`catalog/tencent.py`、`test_catalog_aliyun.py`、`test_catalog_tencent.py`、`test_catalog_diagnostics.py`；修改 backend/pyproject.toml、poetry.lock。

**Interfaces:** 两适配器均实现 `fetch_page(source, query: CatalogQuery, next_token: str | None) -> CatalogPage`；SDK client 由独立 factory 创建，测试可替换，不在导入模块时连接云端。

- [ ] 从官方 API 示例整理脱敏 fixture，写失败测试：镜像名称/架构、规格 CPU/内存、网络归属、可用 IP 数、分页游标、字段缺失、售罄和未知状态的规范化。
- [ ] 运行两个适配器测试，确认失败，再用 Poetry 解析并锁定官方 `alibabacloud-vpc20160428`、`tencentcloud-sdk-python-vpc` 版本；验证与当前 ECS/CVM/common 依赖兼容，提交时同时保留锁文件变更。解析/安装失败保留明确阻塞，不生成假锁文件或跳过依赖。
- [ ] 阿里云使用 ECS 的 DescribeZones/DescribeImages/DescribeInstanceTypes/DescribeAvailableResource/DescribeSecurityGroups/DescribeAccountAttributes，与 VPC 的 DescribeVpcs/DescribeVSwitches；腾讯使用 CVM 的 DescribeZones/DescribeImages/DescribeInstanceTypeConfigs/DescribeZoneInstanceConfigInfos/DescribeAccountQuota，与 VPC 的 DescribeVpcs/DescribeSubnets/DescribeSecurityGroups。实现前按已安装 SDK 与官方请求模型核对参数，禁止凭记忆猜字段。
- [ ] 读取网络与安全组实际所属账号/VPC/地域，返回名称及已声明属性；容量类值统一单位，内存 MiB 不与 GiB 混用。quota 接口未返回某种数量时对应字段为 null，并给出说明。
- [ ] 库存以专门可用性接口为依据；机型配置本身不输出 available=true。查询支持的库存状态映射建立 fixture，未知枚举归 null。
- [ ] 复用 cloud_diagnostics 的脱敏与错误分类，补充实际 operation/API 权限说明及 requestId，避免把子网权限不足统一说成“云主机查询权限不足”。测试缺 SDK、认证、权限、区域、限流和超时，确保 Secret 不出现在返回值。
- [ ] 运行适配器测试和现有 cloud_connection/cloud_sync/private_cloud 回归，确认不改变已有资产发现行为。

### Task 3：计划前与执行前的最终校验

**Files:** 新增 `catalog/validation.py`、`test_catalog_validation.py`；修改 services、tasks、contracts、models、RequestSerializer；生成 `migrations/0006_plan_resource_snapshot.py`，依赖保护计划的 0005。

**Interfaces:** `resolve_request_resources(record, actor, *, refresh: bool) -> dict`，返回规范化资源 ID 与展示属性、策略摘要、读取时间、可用性结果；`validate_resolved_resources(record, actor) -> None` 在执行前重新校验。

新增 `ProvisioningPlan.resource_snapshot`（JSON、只读 API 字段）冻结解析结果；不往 parameters 塞入展示字段，避免破坏 validate_inputs 的参数白名单。生成和执行保存计划的摘要都覆盖 resource_snapshot，执行前刷新只用于校验，不修改已有快照。名称或读取时间变化不单独触发重新审批，资源身份、兼容性或授权变化才使计划失效。

- [ ] 写失败测试：篡改网络/安全组、同名不同账号资源、镜像和规格架构不兼容、镜像不存在、售罄、必要查询失败、创建后目录变化不改写旧计划；旧静态模板按原策略继续校验。
- [ ] 运行 `python -m pytest apps/provisioning/test_catalog_validation.py -q --basetemp=.pytest-provisioning`，确认失败后接入。
- [ ] 创建申请只接受稳定 ID；生成计划时做实时解析，冻结名称、CPU/内存、网络关系及策略摘要。不要以 catalog 缓存作为审批或权限凭证。
- [ ] 执行前检查归属、策略、必要兼容性与可用性；若资源或策略变化影响计划，拒绝并要求新计划，不能静默替换 ID。可用性检查通过也不承诺库存预留。
- [ ] 只有 schemaVersion=2 的新版策略启用动态发现；历史已发布版本不可原地添加 selectors，不因发布新版而给旧申请扩大范围。
- [ ] 跑原有 contracts、lifecycle、execution、reconciliation 回归；如果 state 保护计划已落地，使用其保护测试配置，不关闭保护校验来绕过测试。

### Task 4：共用选择组件与管理员配置联动

**Files:** 新增 `frontend/src/components/business/cloud-resource-picker/index.vue`、`types.ts`、`shared.ts`；修改 `service/api/provisioning.ts`、申请抽屉、资源模板配置页；新增 `frontend/scripts/test-cloud-resource-picker.cjs`。

**Interfaces:** `fetchCloudCatalog(query)`、`fetchCloudConfigurationCatalog(query)` 返回 Task 1 DTO；组件 props 为 kind、versionId、credentialId/sourceId、region 和依赖对象，emit 返回选中 ID 与展示摘要，不返回原始对象。普通和管理员模式由父组件明确传入的 API 能力决定。

- [ ] 编辑前读取 Vue、UI、TypeScript 技能；先写选择依赖与 stale-response 纯函数测试：账号变化清除全部下游，zone 变化清除不兼容镜像/规格/网络，旧序号响应不得更新当前列表，空数量不转成 0。
- [ ] 运行 `node scripts/test-cloud-resource-picker.cjs` 验证失败，再实现复用组件。使用 Element Plus 的带标签表单、可搜索选项、明确加载态/空态、分页“加载更多”、重读按钮和读取时间。
- [ ] 镜像显示名称/系统/架构；规格显示型号、CPU/内存和可用状态；子网显示名称/网段/可用区/IP 余量；安全组显示名称/VPC。缺名称回退到 ID，售罄禁选有原因，未知不涂成成功。
- [ ] 申请与模板页复用组件；管理员通过结构化发现规则配置范围，保留旧版本只读展示。更改上游字段取消或忽略旧请求，不保留上一账号的选择，不提供错误时任意输入 ID 的旁路。
- [ ] 在 frontend 运行组件测试、pnpm typecheck、范围 ESLint、pnpm build；后端跑 catalog 与现有 provisioning 回归及 check/makemigrations --check。
- [ ] 测试环境用只读账号验证真实目录、分页、限流/权限错误、私网关系和库存；浏览器验收桌面/窄屏、长名称、读取失败、售罄与账号切换。真实环境未验证时明确记录，不宣称已完成实云验收。

## 后续阶段

项目配额、审批待办、生命周期及 VMware/OpenStack/PVE 交付不混进目录 API 的权限逻辑；按已确认总设计分别实施。此计划不扩大 Terraform 允许的动作集合，也不将浏览目录等同于拥有创建权限。
