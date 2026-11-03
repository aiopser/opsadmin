# 2026-10-23 全局代码与交付审查

> 本文保留修复前的发现与验证依据。授权修复后的实现、最终检查和未验收项见 [当前状态](current-status.md) 与 [升级说明](2026-10-23-remediation.md)，不要把本文的初始状态当作当前状态。

本轮审查当前工作区，不仅比较某次提交。仓库存在大量未提交变更；未重置、修改业务代码、迁移数据库、连接真实资产或发送通知。本文是审查记录，不表示下列问题已经修复。

审查覆盖：用户与权限、任务单/定时任务/执行器/重试、执行资源与前端编辑器、CMDB 同步、Terraform 交付回读、规范工具与已有交付文档。不是形式化证明，也不能替代浏览器、真实 MySQL 并发和测试云账号验收。

## 一、优先阻断的问题

### R01 / P1：用户管理可写入超管标志

- 位置：`apps/user/serializers.py:9`，`apps/user/views/user_profile.py:83`，`common/auth/rbac.py:8`。
- `UserProfileSerializer` 仅排除 password，`is_superuser`、`is_staff`、groups、user_permissions、role 都是可写字段。用户管理入口没有按操作者限制这些字段；一旦 is_superuser 为真，RBAC 直接放行。
- 触发：拥有用户创建/编辑 API 权限的非超管，提交超管标志。此权限不应自动等于授予超级管理员的权限。
- 已验证：以测试设置加载 serializer，不保存模型；`is_superuser/is_staff` 的 read_only 均为 False，partial 校验接受两个 True。未实际提升任何用户权限。
- 建议：使用显式字段白名单；特权与角色授权单独校验；覆盖创建、完整更新、部分更新和内置管理员保护。

### R02 / P1：定时入口缺少高危执行授权

- 位置：`apps/jobs/serializers.py:612`，`apps/jobs/views.py:785`，`apps/jobs/tasks.py:452`；对照手动入口 `serializers.py:379`。
- 手动运行校验 `automation.command:execute_high_risk`，定时定义、立即执行及 Beat 发起没有同等检查，application 创建服务也没有兜底。
- 触发：用户有定时任务与目标读取权限，没有高危执行权限，选择包含高危命令的已发布流程。手动入口拒绝，定时入口仍可创建运行。
- 验证依据：校验、创建与执行调用链静态核对；未实际执行危险命令。
- 建议：将授权收敛到统一应用服务，并在触发时按当时权限重验；覆盖手动、任务单、定时、克隆和节点重试。

### R03 / P1：秘密参数的源定义仍明文存储和回传

- 位置：`apps/jobs/serializers.py:682`、`:797`、`:585`，`apps/jobs/models.py:160`、`:264`。
- 运行记录使用秘密输入加密，不等于任务单和定时定义安全。后两者仍把 schema 中 `type=secret` 的值存进普通 JSONField，并由 serializer 原样返回。
- 任务单入口 `apps/jobs/views.py:831` 还是全局 queryset，进一步扩大了读取边界。
- 触发：在任务单或定时任务保存带 secret 参数的流程，再读取定义详情/列表。
- 验证依据：字段、保存/读取与运行保护调用链核对；没有读取真实秘密。
- 建议：源定义加密、响应脱敏、编辑保留原值协议，并为历史明文数据提供迁移与核查方案。

### R04 / P1：旧 attempt 的迟到结果可覆盖新重试

- 位置：`apps/jobs/tasks.py:239`，`apps/jobs/node_executors.py:678`，`apps/jobs/execution/registry.py:254`。
- 开始时有 attempt 认领，但完成写入没有以原 attempt/task 身份做条件更新。旧任务返回后重新读取当前 NodeRun，再无条件写结果。
- 触发：attempt 1 超时回收，用户发起 attempt 2，随后 attempt 1 返回；旧结果覆盖新状态/输出，甚至推动下游。
- 已验证：提取原结果写入函数，以内存模型模拟，attempt_count=2 的 running 节点可被旧结果改成 success。未在真实 Worker 注入故障。
- 建议：完成、失败、事件及流式输出均使用执行代次校验；迟到结果只能归属旧 attempt，不能更新当前投影。

### R05 / P1：脚本加载竞态导致选择名称与执行正文不同

- 位置：`../../frontend/src/views/ops/quick-execute/script/index.vue:94`。
- `onScriptConfirm` 没有校验请求代次或当前脚本 ID，也未在加载新脚本时清空旧版本/正文并阻止提交。
- 已验证：提取实际 SFC 函数，模拟 A 慢、B 快；最终选择及任务名称为 B，正文与 sourceCommandVersionId 却属于 A。
- 由于旧 ID 和旧正文彼此一致，后端版本一致性校验无法拒绝该组合。
- 建议：资源身份、请求代次与加载态贯通；切换、重置、关闭和旧响应返回都需回归。

## 二、其余已确认缺陷

| ID / 级别 | 缺陷与影响 | 位置 / 验证 |
| --- | --- | --- |
| R06 / P2 | A 失败后 B/end 被标成 skipped；只重试 A 并成功，仍不会执行 B，最终报 graph stalled。 | `apps/jobs/application/retry.py:31`、`apps/jobs/workflow_engine.py:292`；原函数与内存 ORM 复现。需区分分支跳过与失败阻断。 |
| R07 / P2 | 流程保存请求中继续编辑，成功后快照读取当前表单，把未上传的内容当作已保存，取消离页保护；保存并发布也可能发布旧内容。 | `../../frontend/src/views/task/flow-design/index.vue:677`；实际函数隔离复现。保存快照必须对应提交载荷。 |
| R08 / P2 | 模块参数配置支持 array/object，但快速执行将其字符串插值成 `name=nginx,git` 或 `headers=[object Object]`；后端默认参数转换也需要统一复杂值契约。 | `../../frontend/src/views/ops/quick-execute/module/index.vue:95`；实际函数复现。原有引号用例不覆盖结构化类型。 |
| R09 / P2 | 切换 Git ref 不使旧正文请求和已选文件失效，界面显示分支 B，却导入分支 A 的 Playbook。 | `../../frontend/src/views/automation/resources/modules/command-page.vue:666`；实际函数复现。请求身份必须包含 repository/ref/path。 |
| R10 / P2 | 交付回读新建 Windows 主机时缺少连接默认值，得到空 connection_type、22 端口；inventory 把它归为 Linux/SSH，后续普通同步也不会修正连接配置。 | `apps/provisioning/reconciliation.py:113`；真实模型对象与 inventory 函数的无数据库探针复现。 |
| R11 / P2 | 云同步超时回收已标记 failed，旧 Worker 在最后一条资产处理后仍无条件保存 succeeded 并清空错误，与失败通知矛盾。 | `apps/cmdb/tasks.py:206`、`:222`，对照 `apps/cmdb/sync_automation.py:109`；原终态写入片段复现。需条件更新。 |
| R12 / P2 | 回读任务可重复投递，较新任务已成功纳管后，较旧任务的异常处理仍可把 inventory_status 改回 pending/failed。 | `apps/provisioning/reconciliation.py:154`、`apps/provisioning/views.py:277`；并发窗口代码核对。需认领或执行代次。 |

## 三、必备能力的具体缺口

1. **发起执行的请求级幂等。** 已有 DispatchRecord，保护同一运行的 Broker 投递；未见客户端 Idempotency-Key/请求 ID 唯一约束。HTTP 响应丢失后重发，仍可能创建两个运行。应绑定操作者、载荷摘要与幂等键，不把确认摘要当成幂等锁。
2. **登录安全配置真正生效与会话撤销。** `security.login.max_failures` 目前仅见于配置种子，认证代码没有使用它。密码修改/重置没有完整会话失效链路；应补失败次数/锁定窗口、解锁策略、改密后旧 refresh 失效、默认密码首次修改。重置接口还接受 query 中的 password（`apps/user/views/user_profile.py:184`），应只接受请求正文。
3. **未知执行结果的人工接管与结案。** 已有防重复 apply、state 归档、备份和回读，但 needs_reconciliation 的申请缺少带证据、权限和审计的人工核实/接管入口。不能把直接改数据库作为恢复方法。参见 `apps/provisioning/reconciliation.py:122`、`state_restore.py:20`。
4. **数据范围贯穿运行子资源。** 运行已有 department/all 范围，但节点历史仍 owner-only（`apps/jobs/views.py:979`），有权查看运行的人可能在主机结果、attempts、节点日志上遇到 404。
5. **外部执行的取消语义。** Jenkins 轮询不检查取消，也没有远端 queue cancel/build stop。应明确选择“停止等待”还是“停止远端构建”，让 UI、状态、通知和文档一致，不能让用户误以为远端工作已停止。

这些能力应先于新增菜单和更多云厂商。通知渠道、云同步、审批基础、state 备份/恢复和云目录已经存在，不能再笼统列为“尚未实现”。

## 四、前后端代码规范

### 当前检查结果

- 前端：`pnpm typecheck` 通过；`pnpm exec eslint src --format json` 为 0 error、0 warning，未执行 fix。
- 后端：按现有 Black，对 apps/common/devops 下排除迁移、测试及缓存后的 239 个 Python 文件执行 check，退出 1，74 个文件需要格式化。未改写文件。
- 本轮没有复跑全量业务测试，也没有真实云、通知、主机或生产数据库验收。上一轮的 872 passed/6 skipped 仅为历史自动回归结果，不能覆盖本轮新发现。

### 应成为合并门槛

- 后端 serializer 显式字段白名单；特权字段和关联授权单独验证，避免只用 `exclude=password` 暴露模型字段。
- 执行前授权集中在 application 服务；异步完成集中使用带代次的条件提交，禁止随处分散状态赋值保存。
- 前端异步资源请求统一校验身份；保存成功使用提交时快照；覆盖 double-click、reset、close、旧响应和多类型参数。
- 固定 API DTO 与错误协议。脚本选择组件仍读取 risk_level/updated_at，而服务层已转为 riskLevel/updatedAt；直接断言和宽泛 Record 会掩盖这种错误。
- 动态路由使用路由名。`flow-design/index.vue:778`、`run-create/index.vue:251` 仍有字符串路径，需按仓库规则统一。
- CI 执行不改文件的 lint/typecheck、后端格式与静态检查、pytest、迁移差异检查、OpenAPI 契约和关键浏览器流程。仓库未发现 `.github/workflows`，若使用外部 CI，需把等价配置及通过条件纳入版本管理。

### 渐进治理

- 当前 `frontend/package.json:42` 的 lint 带 `--fix`，建议拆成 lint 与 lint:fix；不能用会修改工作区的命令作为唯一 CI 检查。
- 规范统一前先确立基线，避免一次格式化所有历史文件掩盖业务改动。先对新改代码阻断，再分批清理 74 个存量文件。
- 拆分职责过多的业务文件，优先请求生命周期、表单快照、参数序列化、版本管理等明确边界，而非按行数机械拆分。当前 command-page.vue 1592 行、run-detail 1329 行、flow-design 1295 行，jobs serializer/view 也超过 1500 行。
- UI 规则应有少量共享组件和交互回归支撑。现有 ESLint 全通过，并不表示表单状态、DTO 兼容、颜色和布局规则都已经自动检查。

## 五、必须补齐或校正的文档

| 文档 | 具体缺口 |
| --- | --- |
| 项目入口 README 与文档索引 | 根目录没有项目 README；前端 README/教程仍以框架为主。需要架构、当前功能矩阵、目录、开发命令和文档入口。 |
| 当前部署与升级手册 | deployment.md 仍写未执行部署；已有多实例及 Runner 实验记录，应区分隔离验收与正式部署状态。明确 API/ASGI/Worker/Beat 启动、队列、版本一致性、健康检查和回滚顺序。 |
| 当前验收矩阵 | testing.md 仍保留 15 项旧失败；acceptance.md 仍是 370 passed，部分总表状态与子报告不一致。历史记录保留，新增权威当前状态，分别列 mock、SQLite、MySQL、Runner、浏览器、实云和压测证据。性能复测不能直接算通过。 |
| 安全与权限手册 | 角色/API/资产/高危执行/数据范围矩阵、秘密参数协议、改密和会话撤销、凭据轮换、出站访问与审计边界。 |
| 云 IAM 最小权限附件 | 已有目录只读动作清单；实际创建/轮询的 RAM/CAM 写动作仍是原则性描述（resource-provisioning-deployment.md:138）。应按锁定 Provider 补动作、资源/地域限制和拒绝测试证据。 |
| 故障恢复 Runbook | 未知 apply、重复回读、Worker 失联、积压、备份损坏、磁盘满、通知失败；明确何时可重试、何时只回读、何时需人工接管。数据库、凭据密钥、Terraform state 和日志恢复须配套演练。 |
| 开发贡献规范与 API 契约 | 统一字段命名、时间/时区、分页、错误体、事务/锁顺序、幂等、状态机、secret 处理、前端请求代次和表单保存语义；补后端规范与统一 CI 命令。 |

## 六、建议顺序

1. 先处理 R01–R05 的权限、保密与执行正确性问题，并加入负向/竞态回归。
2. 再处理 R06–R12，补定义层秘密、跨入口权限、并发代次及复杂参数的契约测试。
3. 补请求级幂等、未知结果接管和登录安全，再收敛 CI 与当前文档索引。
4. 在隔离环境完成真实 MySQL 并发、Worker 故障、云账号最小权限与关键浏览器验收，再决定继续扩功能。
