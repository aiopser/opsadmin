# 蓝鲸能力对照后的增量优化记录

日期：2026-10-09。分支：`dev2`。基准提交：`b9fc9fc4d4a1437a154dce7e021cfe559d500952`。

工作区已有大量暂存及未暂存改动，本轮修改叠加在现有代码上，未重置或覆盖整个文件。
不清空已有数据库，不连接生产资产。本文记录本轮实际进度，不替代原 V2 重构计划和内网验收报告。

## 阶段 1：工作流版本保存契约

- 前端 `fetchUpdateWorkflowVersion` 使用原始 camelCase 请求，与 `WorkflowVersionSerializer` 的显式字段对应。
- 编排页保存草稿始终提交 `inputSchema` 和 `globalVars`，包括空对象，支持清空已保存配置。
- 保留嵌套业务参数原始键名，不递归转换用户数据。
- 新增前端请求契约测试，以及真实 Django REST 更新、清空、重新查询测试。

涉及文件：`frontend/src/service/api/automation.ts`、`frontend/src/views/task/flow-design/index.vue`、
`frontend/scripts/test-workflow-version-contract.cjs`、`apps/automation/test_workflow_version_dto.py`。

删除：删除该接口的错误字段转换调用，以及跳过空对象提交的分支；未删除业务文件或 API。

## 阶段 2：历史快照重跑与当前资产执行

- 重跑及失败重试克隆原运行的目标快照、流程图和执行配置。
- 新增 `cmdb.targets.authorize_frozen_targets`：检查当前用户资产权限、资产启用状态，以及快照原凭据引用的存在、启用状态和访问权限。
- 主机重新绑定凭据后，重跑仍验证原凭据，不能借此绕过原凭据停用。
- 从任务单或作业执行页创建新运行仍解析当前资产并建立新快照。
- 前端运行详情页及作业详情抽屉均提供重跑语义说明，包含中英文文案和国际化类型。
- 更新两个接口测试使用真实完整目标快照，增加完整快照相等断言；修正一个已有超时测试的旧夹具，保留资源超时上限断言。

涉及文件：`apps/cmdb/targets.py`、`apps/jobs/application/runs.py`、`apps/jobs/test_execution_entrypoints.py`、
`apps/jobs/test_ops_api.py`、`apps/jobs/tests.py`、`frontend/src/views/task/run-detail/index.vue`、
`frontend/src/components/business/run-detail-drawer/index.vue`、`frontend/src/locales/langs/{zh-cn,en-us}.ts`、`frontend/src/typings/app.d.ts`。

删除：克隆路径中按当前 CMDB 重建目标连接信息的行为。未增加旧字段别名或不完整快照回填。

本阶段未改变“失败重试克隆新运行”的现有行为，不宣称只重试失败节点。
凭据快照保存引用，不保存历史密码或私钥；执行时仍读取当前有效的凭据秘密。

## 待实施阶段

1. 已完成：统一任务单、定时任务及直接运行的主机/组/标签目标选择器，保存原始选择条件与解析快照。
2. 按“显式选择网关，否则直连”清理主机默认网关的无效模型、字段、页面及测试。
3. 完善步骤参数及输出映射，继续使用步骤条界面。
4. 核验各入口的权限、安全检查与审计覆盖。
5. 当前代码的内网集成回归及性能复测。已有内网报告是历史证据，不重复标记为未做，也不视作当前代码全部通过。

数据库迁移仅在模型改造阶段生成和审查；本轮不运行部署数据库迁移。

## 验证

前端：请求契约和事件流测试 6 项通过；修改文件 ESLint 零警告通过；`pnpm typecheck` 通过。
后端：本次相关的接口、目标和执行入口测试 39 项通过；全量测试 465 通过、6 跳过、17 个子测试通过，耗时 96.18 秒。

实际命令：

```powershell
# frontend/ 下执行
pnpm exec node --test scripts/test-workflow-version-contract.cjs scripts/test-run-event-stream.cjs
pnpm typecheck
pnpm exec eslint src/service/api/automation.ts src/views/task/flow-design/index.vue src/views/task/run-detail/index.vue src/components/business/run-detail-drawer/index.vue src/locales/langs/zh-cn.ts src/locales/langs/en-us.ts src/typings/app.d.ts scripts/test-workflow-version-contract.cjs --max-warnings 0

# backend/ 下执行，devops.test_full_settings：SQLite 内存库、内存缓存/消息代理
.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest_cache/optimization-20261009-b728
```

回归先验证失败：前端两个契约用例因字段转换失败；后端两个用例分别复现目标漂移和原凭据停用未被拒绝。
第一轮全量出现三项失败：两个接口测试的快照夹具不完整，以及一个已有测试没有使用冻结执行配置；更新夹具后保留原业务断言，最终全量通过。
Windows 沙箱路径解析及默认 pytest 临时目录出现权限错误；通过在授权检查环境中运行、使用独立工作区测试临时目录解决，未修改依赖包或跳过迁移来掩盖问题。

尚未运行：浏览器实际交互、当前代码的真实 MySQL/Redis、多实例、隔离 Runner 和性能复测。本次内存测试不替代这些验收。


## 阶段 3：统一目标选择（2026-10-09）

变更清单：
- CMDB 统一规范化主机、分组、标签 ID，按并集去重；拒绝不存在的标签，逐项验证目标访问权限。
- 任务单和定时任务保存原始选择；运行持久化 targetSelector 与 targetSnapshot。每次新运行解析当前成员，重跑仍沿用原快照。
- 前端新增共享 target-selector-fields 组件，接入任务单、定时任务及直接执行抽屉，分页加载完整分组和标签选项；列表与任务详情展示三类选择数量。
- 定时任务局部更新改用 PATCH，避免仅切换启用状态时缺少 name 被拒绝。
- 新增 jobs/migrations/0015_target_selectors.py，只生成与检查，未应用到已有数据库。

删除清单：删除 from_host_ids 专用入口，统一为 create_workflow_run_from_selector；删除直接运行接口中标签缺失被静默忽略的旁路；删除任务单/调度器重复目标校验。不增加旧入口别名。

实际验证：全后端 468 passed、6 skipped、17 subtests passed（100.16 秒，隔离测试数据库）；之后 PATCH 目标保留回归 3 passed。前端 pnpm typecheck 通过；本阶段修改文件 ESLint 通过，接口文件换行警告已修复。makemigrations --check --dry-run 显示 No changes detected。

未完成：浏览器交互验收；真实隔离 MySQL/Redis、多实例及性能复测；后续网关清理、步骤参数输出映射和权限安全审计覆盖。已有数据库和生产资产未操作。
