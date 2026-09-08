# V2 执行记录

## 授权与边界

用户于 2026-09-07 追加授权持续按计划完成，不因常规阶段确认而中断。现有基线失败按新契约逐模块处理；不恢复旧兼容接口。不清空任何已有数据库、不连接生产资产、不部署或推送。

## P0 / T01

详见 testing.md 和 test-collection-t01.txt。236 项收集，221 通过、15 失败；新增隔离回归通过，系统及迁移差异检查通过。新增 test_mysql_settings.py 只接受明确 opt-in、独立非默认本机端口和随机新库名，不读取部署数据库凭据。

真实 MySQL 验证未完成：本地 Docker Engine 管道不存在，未发现已提供的隔离 MySQL 实例。未改用其他地址。15 项现有契约失败保留，随对应模块重新覆盖；没有标记全量绿灯。删除清单为空。

## P0 / T02

安全行为已实施：body-only refresh、本人 token 吊销、禁用用户拒绝、错误及操作日志脱敏、独立凭据密钥、生产配置和前端退出调用。变更涉及 user/views/auth、common/exception/redaction、jobs/events、permission/middleware、cmdb/crypto、devops settings 和前端 auth API/store/user-avatar。

删除：query refresh 回退、旧 SECRET_KEY 派生加密/吞掉解密异常、jobs 私有重复文本脱敏函数、全局 DJANGO_ALLOW_ASYNC_UNSAFE 设置；没有删除测试或模型。11 项新增安全测试从失败到通过，带 Runner 脱敏专项共 18 项覆盖（两次命令分别 16 和 11 项，有交集）。全量 247 项：232 通过、15 项原基线失败，13 subtests 通过。迁移差异检查无变化。前端直接运行现有 vue-tsc 和 ESLint 均退出 0；普通 pnpm 因运行器版本触发依赖重装提示，未执行清空 node_modules。

生产 check --deploy 退出 0，5 项现有 schema 警告，详见 security-configuration.md。真实部署未执行。依赖升级作为后续独立提交继续处理。

### T02 依赖升级（2026-09-08）

Poetry 锁定 Django 5.2.17、DRF 3.16.1、Channels 4.3.2、Daphne 4.2.3、django-filter 25.2、cors-headers 4.9.0、SimpleJWT 5.5.1、channels-redis 4.3.0；Python 3.12.10。移除不再需要的传递依赖 pytz。官方支持依据：https://www.djangoproject.com/download/ ，https://www.django-rest-framework.org/community/3.16-announcement/ ，https://channels.readthedocs.io/en/latest/releases/4.2.1.html 。

实际全量回归 232 passed / 15 原基线 failed / 13 subtests passed（48.84 秒），系统检查与迁移差异检查通过。未把原基线失败忽略为成功。Ansible 真实隔离执行及其他外部集成仍待 T07/T15。

## P1 / T03 审计契约

实现按 actor 限制普通用户 list/detail/export，超管可读取全量；纯 ReadOnlyModelViewSet 保留项目 envelope 和分页。快照递归脱敏，新增 run_id/result 和实际生成的 0002 迁移。唯一 camelCase 字段输出，前端已有 audit API 同步类型。导出为分页迭代的 NDJSON 流，单独 audit.event.export 权限。

删除：StandardModelViewSet 可写基类继承、serializer 的 snake_case + camelCase 双输出。未删除业务能力或旧测试。新增 10 个业务用例（包含方法参数化），审计模块 14 passed；完整回归 242 passed / 15 原基线 failed / 13 subtests passed（50.71 秒）。迁移差异、前端 vue-tsc 与 ESLint 通过。现有用户/角色页面为 UI 样板，审计页面保持原有 useUIPaginatedTable/ElementPlus 抽屉。

未完成：MySQL 真实迁移和浏览器联调；未提供面向普通用户的清理 API。新迁移仅在测试空库运行，最终迁移重建仍在 T09。

## P2 / T04 目标快照

新增 cmdb/targets.py 作为 resolve_targets/snapshot_targets 唯一授权入口，锁定并重读资产，校验组/资产/凭据权限及状态。快照只包含 host_id、hostname、address、port、connection_type、credential_ref_id、variables；variables 使用严格白名单 Schema，网关引用放 gateway_ref_id，拒绝密码等任意连接变量。CredentialRef 新增 is_active；读取执行凭据再次拒绝停用项。jobs 创建、serializer、事件投影与 inventory 同步新字段。

删除：jobs.build_host_snapshot、jobs 内重复目标查询、旧 ip/connection_port/ansible_connection_vars 快照字段、旧 mock ORM 形状锁测试。其业务替代为目标状态重验、快照不变及权限测试；creation_governance_tests 改为真实模型持久化测试。网关执行和 inventory 旧测试仅更新输入/输出字段及显式授权 fixture，未降低业务断言。

专项 10 passed；相关回归 155 passed / 3 原失败（该命令早于新增执行期停用用例）。最终全量 252 passed / 14 原失败 / 13 subtests passed（53.40 秒）；迁移差异检查通过，旧 build_host_snapshot 全库 Python 引用清零。新增 cmdb/0009 在 SQLite 测试新库执行；MySQL 锁语义和迁移未验证。前端资产主数据 API 未变，执行详情新快照展示统一在 T14 对齐。

## P2 / T05 WorkerPool

WorkerPool/serializer/view/admin 仅归 jobs，表 jobs_worker_pool，唯一 API /api/v1/jobs/worker-pools。jobs 外键、所有运行时 import、权限种子与测试同步。新增 worker_pools.py 的权限、停用、execution_kinds 与队列校验；作业创建和节点队列均接入。创建/更新/删除有显式审计，初始化命令 init_worker_pools 幂等且不重置已有配置。

删除：CMDB WorkerPool 模型、serializer/view/admin、旧路由、init_cmdb_defaults；旧 CMDB 引用仅存在历史迁移（T09 统一重建）和断言旧路由 404 的负向测试。原 CMDB config_summary 测试中池断言移至 jobs 的 API/队列用例，资产配置断言保持。

专项 worker pools + CMDB 17 passed，最终全量 258 passed / 14 原基线 failed / 13 subtests passed（54.97 秒），迁移差异检查通过。新增 jobs/0025、0026 与 cmdb/0010 仅测试空库执行，无历史池数据搬迁。未验证真实 Worker 在线/失联、真实凭据临时文件生命周期（T06/T07），未声称 SQLite 等价 MySQL。

## P3 / T06 唯一执行契约

新增 ops/contracts.py 与 AnsibleExecutor.execute；jobs 两条当前运行路径、CMDB 资产连接探测和事实采集直接使用统一执行器。RunnerEvent 在边界脱敏并保留未知事件；无主机回调、失败主机回调均不能被退出码 0 覆盖。取消、超时、异常及执行自有目录生命周期有专项测试。凭据私钥改为执行目录内唯一临时文件，移除全局固定凭据文件；执行前重验资产授权/状态，保留原运行快照。连接测试现只接受 hostId，使用资产绑定凭据和网关；事实采集必须提供 actor_id。仓库前端没有调用这两个旧协议的代码。

删除：ops/workflow/adapters.py、plans.py、ansible_service.py 和 ops/services.py；AnsibleExecutionInput、旧 Callback stdout 打印、inspect.signature 适配及固定全局 SSH key 文件逻辑。旧包装测试替换为 execute 业务契约、no_log/临时目录/adhoc 参数测试；未删除失败业务断言。缺失环境凭据测试改用真实 CredentialRef 对象修复原不完整替身。

实际测试：执行器 12 passed；CMDB 授权/私钥成功及异常清理 3 passed；jobs Ansible + 执行前停用 20 passed；最终全量 270 passed / 13 原基线 failed / 13 subtests passed（57.72 秒）。compileall 通过，diff 空白问题已修复。没有连接任何真实目标。

未完成：真实 SSH/WinRM/网关集成属 T07；自有迁移重建 T09；底层旧 tasklog 日志链 T11。当前 services.py 的职责拆分及统一创建入口在 T08/T13，旧 Runner Adapter/Service 入口已删除。

## P3 / T07 隔离 Runner 集成（未完成）

新增 test_runner_integration.py 的 localhost-only 真 Runner 成功/失败/取消用例及 runner-validation.md。默认必须显式 opt-in 且使用 Linux 控制节点；实际本机执行结果 3 skipped，原因是没有隔离 Worker opt-in，未算通过。Docker 只读版本探测失败，daemon 管道不存在；没有启动容器或连接真实主机。删除清单：无。真实隔离成功/失败/取消与多主机、SSH key、网关、WinRM 均未验证。按用户连续推进授权继续 T08，保留 T07 验收缺口。

## P4 / T08 提交、领取与职责拆分

新增 application/{runs,dispatch,cancel,retry}.py、execution/{plan_builder,registry}.py；运行创建、计划构造、执行、取消、重试和 Broker 投递直接引用职责模块。投递失败记录 dispatch_failed，后续仅重新投递未领取工作；不把 Broker 故障当执行失败。节点投递携带 attempt，领取 CAS 校验 attempt 和取消/终态；显式重试创建新 attempt，旧投递不能领取它。事务回滚不投递；HTTP 取消保持 cancel_requested，运行节点退出前图调度器不提前取消；失联恢复记录未确认结果，不声称取消成功或重跑命令。

删除：jobs/services.py 全部旧导出，无转发壳；tasks.py 内重复 enqueue 定义与缺失 Celery 时同步执行的回退；views 内非原子重试实现。request_execution_cancel 从 recovery 移到 application/cancel。旧线性 run_workflow_ansible 实际实现暂在 execution/registry（T13 收敛时删除），不是 services 兼容导出。

实际验证：调度契约 9 passed。全量首轮 279 passed / 13 原基线 failed / 3 T07 明确 skipped / 13 subtests passed（58.00 秒）。随后取消/超时映射与失联语义补验：jobs/tests.py + 调度契约 86 passed / 1 原图表达式失败 / 15 subtests passed（18.80 秒）。旧 jobs.services/Celery fallback 引用清零，git diff --check 通过。

未完成：真实多 Worker/Redis 故障集成、MySQL 并发锁语义；事件持久化目前仍多处写入，T09 统一并加 sequence/幂等约束。恢复调度记录查询的批量效率在后续事件索引及 T15 验证。

## P4 / T09 事件序列、幂等投影与新迁移基线

新增 append_run_event 唯一事件写入口，run 行锁分配 sequence；event_key 按 node/attempt 隔离，同事务写日志及投影；重复返回已有事件。新增 run.event_sequence、事件 sequence/event_key/attempt 及数据库唯一约束；投影记录 last_sequence/attempt，拒绝旧 attempt 和乱序 counter 覆盖，终态不会回退到运行态。仅对 MySQL 1205/1213 做最多三次事务重试。全部内部事件和 Runner 调用直接更新。

删除：persist_runner_event、所有运行时旁路 JobEventLog.objects.create（仅唯一入口保留）；80 个项目历史迁移源文件及历史 ops label；三项旧回填迁移测试替换为新空库实际数据库约束/事件幂等测试。实际 makemigrations 生成 11 个 initial 文件，保留第三方迁移，不提供旧库升级或数据回填。详见 migration-baseline.md。

专项事件 9 个可执行用例通过，MySQL 并发用例明确 skipped；最终全量 288 passed / 11 原基线 failed / 4 明确 skipped / 15 subtests passed（95.23 秒）。4 skipped 为真实 Runner 3 项和 MySQL 并发 1 项。两项 automation 原种子干扰失败随新空库基线消除。SQLite 测试新库建库、迁移差异检查通过；Black 使用项目可写缓存完成格式化，diff --check 通过。

未完成：MySQL 空库和并发真实验收、外部集成；T10 实时通知尚未接入，T11 stdout 归档尚未实现。没有连接或清空已有数据库。
