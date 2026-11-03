# 当前状态与文档索引

更新日期：2026-10-24。此文件统一记录当前工作区实现、证据与待验收项；它不表示生产已经部署。原始问题见 [全局审查](2026-10-23-global-review.md)，本轮变更与迁移见 [修复与升级说明](2026-10-23-remediation.md)。

历史 `testing.md`、`acceptance.md`、`deployment.md` 及 `acceptance-results/` 保留当时记录；其中的失败数、通过数与部署状态都不能直接替代本轮结论。

## 审查问题的当前实现

| 问题 | 当前已落盘的行为 | 定向证据入口 |
| --- | --- | --- |
| R01 用户管理特权字段 | Serializer 明确白名单，拒绝特权与内部安全字段；角色分配校验可授予权限和数据范围，防止用空权限的 all 范围角色扩大可见性 | `apps/user/test_review_security_oct23.py` |
| R02 定时入口高危授权 | 创建、克隆、节点重试及 Worker 执行前统一按当前活跃用户/角色重新授权；快速执行校验来源内容绑定，缺失元数据按高危处理 | `apps/jobs/test_review_execution_oct23.py` |
| R03 定义层秘密值 | 任务单与定时定义秘密输入加密保存、响应脱敏、保留原值编辑；历史明文由 jobs.0020 迁移保护 | `apps/jobs/test_definition_secrets_oct23.py`；迁移说明见下 |
| R04 旧 attempt 迟到写入 | 完成、失败、控制台、心跳按原 attempt/task/running 状态条件提交；旧日志不覆盖当前主机投影，也不推进新执行 | `apps/jobs/test_review_execution_oct23.py` |
| R05 脚本资源加载竞态 | 请求代次、脚本 ID 与类型绑定；切换/reset/卸载清除旧正文和版本，加载中禁止执行，迟到预览不再弹出 | `frontend/scripts/test-review-frontend-races.cjs` |
| R06 失败后的下游重试 | 恢复失败阻断的 skipped，以及 Worker 丢失恢复时标记“从未开始”的 canceled 下游；保留条件分支和用户取消，清理旧任务身份 | `apps/jobs/test_review_execution_oct23.py`、`apps/jobs/test_final_review_boundaries.py` |
| R07 流程保存快照 | 图载荷拥有独立参数快照；成功后保存提交时快照；保存中锁定编辑/重复提交，存在新变化则阻止发布 | `frontend/scripts/test-review-frontend-races.cjs` |
| R08 模块复杂默认参数 | 数组/对象按 JSON 序列化后转义；前后端统一结构化值与 token 解析契约 | `frontend/scripts/test-module-default-args.cjs`；后端专项回归由联合结果索引 |
| R09 Git ref 竞态 | 文件列表和正文绑定 repository/ref/path；变更 ref、清空文件、换来源或关闭抽屉使旧请求与正文失效 | `frontend/scripts/test-review-frontend-races.cjs` |
| R10 Windows 纳管连接默认值 | 新主机复用 CMDB 默认值，Windows 进入 WinRM/5986；更新已有资产保留手工连接配置 | `apps/provisioning/test_review_reconciliation.py` |
| R11 云同步迟到终态 | Collector 结果及成功/失败提交均受 queued/running 状态条件约束；回收后的旧 Worker 不能改回成功或清空错误 | `apps/cmdb/test_review_sync_fencing.py` |
| R12 重复回读覆盖 | 认领 reconciliation_token，完成/失败同时校验 token 与 state_generation；旧任务不能覆盖新成功 | `apps/provisioning/test_review_reconciliation.py` |

表中“已落盘”表示实现和回归入口已经加入；是否达到发布门槛以最终联合检查和下方环境矩阵为准。

## 新增安全与恢复能力

- 请求幂等绑定操作者、接口路径、请求 ID 与载荷摘要。预览生成 `executionRequestId`，快速执行、流程页、历史弹窗/抽屉、任务单与定时立即执行均透传；同次确认重试复用 ID。过期响应压缩保留 tombstone，不能因清理响应而重新执行旧请求。
- `security.login.max_failures` 参与登录锁定；修改/管理员重置密码更新认证版本，使旧会话失效；新建/重置账号须先改密。前端登录与会话恢复均引导命名路由 `user-center`，改密后重新登录。
- 节点历史、attempt、主机结果与日志沿用运行的 owner/department/all 可见范围。
- Jenkins 取消采用停止本平台等待语义；本地结果标记 `WAIT_CANCELED`，不调用远端停止，也不宣称远端构建已被 ABORTED。界面取消确认明确提示构建可能继续。
- 资源申请新增人工核实结案的预览/确认入口。服务端校验审批身份、state/备份完整性、代次与云端全量证据，确认后再校验并纳管；不会重新运行 Terraform。缺 state、数量不完整、冲突或部分创建仍保持待核实。

详细权限、秘密协议、故障处理与保留策略见 [安全与恢复 Runbook](security-and-recovery-runbook.md)；实际云账号权限清单与拒绝测试见 [云 IAM 验证附件](cloud-iam-validation.md)。

## 最后独立复核的补充修复

- 冻结的主机凭据在真正执行时重新鉴权。主机后来改绑凭据不会替代本次快照原凭据的授权检查，应用边界也使用重新读取的当前操作者。
- Terraform 计划、初始化后和 apply 前验证当前活跃/在职身份及凭据使用权限；周期云同步在采集前后、每条资产写入前重验责任人权限。资产提交锁定同步记录，避免超时回收夹入状态检查与写入之间。
- 普通用户资料保存不能回写旧密码、认证版本与登录锁定字段；旧密码摘要升级使用 CAS，保留强制改密标记，不能覆盖并发重置。
- 幂等回放仍走当前详情对象的数据范围校验；去重记录不是重新读取他人作业的通道。
- 自定义 API 的真实请求/响应补充 OpenAPI DTO；公共响应文档统一为 code/data/msg，严格生成必须零错误、零警告并与提交的 schema.yml 相同。新增字段与通道秘密读写差异有契约断言。
- 测试设置先使用空配置文件路径与虚构基础环境，再载入共享设置，禁止读取部署 INI。独立子进程守卫验证这条规则，不依赖本机部署配置。

执行与云权限补充用例在 `apps/jobs/test_final_review_boundaries.py`、`apps/provisioning/test_final_review_authorization.py`、`apps/cmdb/test_final_review_authorization.py`，先复现 7 项失败，再验证修复。密码并发与幂等范围用例分别在 `apps/user/test_review_credential_concurrency.py`、`apps/jobs/test_idempotency_oct23.py`。

## 验证矩阵

2026-10-24 联合检查结果如下；这是当前工作区的自动验证，不沿用或累加旧报告的通过数。

| 环境 / 检查 | 当前证据边界 | 最终结果 |
| --- | --- | --- |
| 后端隔离 SQLite / mock 回归 | 完整迁移，覆盖权限、秘密、代次、重试、云同步、人工核实与接口契约；不连接真实资产 | **1011 passed、6 skipped、39 subtests passed**；2 条第三方弃用警告 |
| 前端实际函数 / Vue watcher / SSR | 实际 SFC 函数、Vue 响应式、表单渲染；覆盖乱序响应、保存、幂等 ID 和改密导航 | **67 passed、0 failed** |
| 前端 typecheck / 非修改型 ESLint / build | pnpm typecheck、pnpm lint、pnpm build | 全部退出 0 |
| Django check / 迁移差异 | devops.test_full_settings，不读取部署 INI | check 无问题；makemigrations --check 显示 No changes detected |
| OpenAPI 严格校验与快照 | --validate --fail-on-warn，另生成文件逐字比较 schema.yml | 退出 0、零错误/告警；快照完全一致 |
| Python 格式门禁 / 独立检查回归 | 250 个生产文件；63 个历史格式例外仅允许原内容哈希，不代表全仓 Black 合规 | 0 failures；门禁与配置隔离 **8 tests passed** |
| 当前版本真实 MySQL 迁移与并发 | 历史 MySQL 报告属于旧版本，本轮新增迁移和竞争窗口未在真实 MySQL 验收 | 未验收 |
| 当前版本真实 Redis、多 API/ASGI/Worker、Broker 故障 | 历史多实例实验不覆盖本轮协议与恢复变化 | 未验收 |
| 真实主机 / Jenkins / 通知接收端 | 单元替身不能证明远端执行、WinRM、取消或通知交付 | 未验收 |
| 关键浏览器流程 | SFC 函数与 watcher 回归不是浏览器端到端验证 | 未验收 |
| 真实云 CLI/Provider/IAM 与创建/回读 | 需要专用测试账号、固定版本和拒绝测试证据 | 未验收 |
| 压测、恢复演练与生产部署 | 无本轮容量或正式部署证明 | 未验收 |

6 项跳过包括 3 项必须使用真实隔离 MySQL 的并发测试、3 项需明确 opt-in 的 Linux Ansible Runner 集成测试。2 条警告来自 django-celery-beat 使用 datetime.utcnow()；未修改第三方库源码，不能把它们写成已消除。OpenAPI 零警告与 pytest 的这两条第三方警告是不同检查结果。

最后联合命令（在 backend/ 执行）：

```text
poetry run python -m pytest -q --tb=short
poetry run python -m unittest discover -s scripts -p "test_*.py"
poetry run python scripts/check_python_format.py
poetry run python manage.py check --settings=devops.test_full_settings
poetry run python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings
poetry run python manage.py spectacular --validate --fail-on-warn --settings=devops.test_full_settings --file <临时文件>
```

生成契约的 SHA-256 为 `245c30cf5be7a399940ff21e57158acd129027fb49bc883ac2835ff69ae12142`。前端在 frontend/ 使用 `pnpm test:contracts`、`pnpm lint`、`pnpm build` 后再 `pnpm typecheck`；Windows 本地依赖目录读取曾受沙箱限制，提升依赖读取权限后上述标准命令均实际通过。

GitHub Actions 配置已加入仓库，尚未推送触发远端 CI 或设置分支保护；本地通过不能代替远端冷安装、Linux 构建和分支保护验收。

## 迁移与部署门槛

本轮新增迁移为 `user.0002_security_session_policy`、`jobs.0020_definition_secret_inputs`、`jobs.0021_execution_request_key`、`provisioning.0005_reconciliation_ownership`、`provisioning.0006_manual_resolution_evidence`。

jobs.0020 包含无反向函数的数据加密迁移，不能只回滚应用代码。升级前备份数据库、已有凭据加密密钥、state 密钥及私有制品，停止定义写入与执行消费，并在隔离 MySQL 副本验证完整迁移与恢复方案。API、ASGI、全部普通/专用 Worker、Beat 和前端必须使用同一发布版本。

具体顺序与真实启动入口见 [本轮升级说明](2026-10-23-remediation.md)。

## 文档索引

| 文档 | 用途 |
| --- | --- |
| [项目入口](../../README.md)、[贡献约定](../../CONTRIBUTING.md) | 架构、目录、开发与提交入口 |
| [开发质量门槛](development-quality.md) | 后端规范、非修改型检查与 CI |
| [本轮审查](2026-10-23-global-review.md)、[本轮修复](2026-10-23-remediation.md) | 原始触发条件、当前实现、回归与升级 |
| [安全与恢复 Runbook](security-and-recovery-runbook.md) | 权限、秘密、会话、幂等、未知结果和恢复 |
| [云 IAM 验证附件](cloud-iam-validation.md) | 锁定 Provider 的权限与拒绝测试证据 |
| [资源申请部署](resource-provisioning-deployment.md) | 受控 Terraform 环境、state/备份、专项验收 |
| [Ansible 资源变量契约](ansible-resource-variables.md) | 默认参数、输入映射与执行变量 |
| [实时事件](realtime-events.md)、[日志制品](log-artifacts.md) | 事件游标、实时通道与共享归档 |
| [历史测试](testing.md)、[历史验收](acceptance.md)、[历史部署](deployment.md) | 保留原始证据；当前结论以本页为准 |
