# V2 删除验收台账

对照基准 fb7d1e3 与 HEAD 8ea61b9，并检查工作区。源码可通过 Git 历史恢复；本轮未删除数据库或运行数据。

## 已删除文件

| 原文件 | 业务替代 |
| --- | --- |
| apps/cmdb/management/commands/init_cmdb_defaults.py | jobs/management/commands/init_worker_pools.py |
| apps/jobs/services.py | jobs/application 与 jobs/execution |
| apps/ops/services.py | ops/executor.py |
| apps/ops/workflow/adapters.py | ops 执行契约及目标解析 |
| apps/ops/workflow/ansible_service.py | ops/executor.py |
| apps/ops/workflow/plans.py | jobs/execution/plan_builder.py |
| apps/ops/tasklog/__init__.py | 旧模块整体移除 |
| apps/ops/tasklog/constants.py | jobs 事件与归档配置 |
| apps/ops/tasklog/consumer.py | jobs/realtime/consumer.py |
| apps/ops/tasklog/logger.py | jobs/log_artifacts.py |
| apps/ops/tasklog/routing.py | jobs/realtime/routing.py |
| apps/ops/tasklog/signal_handler.py | 显式事件及归档，不再捕获全局日志信号 |
| apps/ops/tasklog/utils.py | jobs/log_artifacts.py |

## 符号与协议

- run_workflow_ansible、_claim_workflow_run、_mark_workflow_failed、views._clone_run 已删除，统一创建与图调度替代。
- InvalidTargetHosts 已删除，使用当前 ValidationError/PermissionDenied，无异常兼容壳。
- persist_runner_event 由 append_run_event 替代。
- /api/v1/jobs/events 已删除，运行域 events 子资源替代；旧地址 404 负向测试保留。
- after_id 明确拒绝，使用 cursor/sequence；拒绝实现和负向测试保留。
- bpmn_xml、runner_workspace 已从模型删除，后续 RemoveField 迁移仍保留，不能按字段名命中直接删迁移。
- 两个前端请求层的静态 apifoxToken 已删除。

历史迁移重建见 migration-baseline.md，业务测试及阶段结果见 refactor-progress.md。

## 尚未关闭

- permission/views/menu.py 仍有 LEGACY_COMPONENT_TO_VIEW 转换，需要同步种子及业务测试后移除。此前“全部兼容符号已清零”的表述范围过大。
- backend/.test-deps 仍存在；需核对引用和精确目录后清理，尚未删除。
- 未使用依赖、废弃文档尚无完整逐项审计证据，不勾选总验收该项。
- T14 普通角色和 ops 角色完整联调、日志和操作链路仍缺完整证据。
- 内网性能未通过；按用户指示暂缓报告细节，不改判通过。

## 本轮 T14 修正

移除运行列表无功能的默认新增/批量删除按钮，修正筛选提示；主机结果请求接入 AbortSignal，迟到响应不能覆盖新请求的加载状态。相关 ESLint、项目 vue-tsc 检查通过。本轮无整文件删除。
