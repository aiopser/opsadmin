# DevOps 直接重构 Implementation Plan（V2：不保留历史实现）

> **For agentic workers:** 使用 superpowers:executing-plans 按任务顺序执行；默认单代理，不自动并行。每个任务先测试、再实现、再回归、再审查。本文仅为计划，不代表已实施或验证通过。

**Goal:** 在用户的新分支上直接重构 Django DevOps，删除旧实现、旧协议和兼容层，建立唯一的资产、执行、调度、编排及实时事件闭环。保留需要的业务能力，不保留其历史实现负担。

**Architecture:** 保持模块化单体，按目标职责直接调整模型、接口和目录；Celery 承担后台执行，MySQL 保存业务状态及结构化事件。Channels/Redis 提供实时通知，REST 负责快照、历史查询和断线补偿。不双写、不保留旧路由、不做旧数据升级链，前后端按新契约配套交付。

**Tech Stack:** 现有 Python、Django/DRF、MySQL、Redis、Celery、Ansible Runner、Channels；版本以重新核验后的锁文件为准，不从附件中的 .test-deps 继承运行环境。

**Spec:** 本文第 1—4 节是本次执行所依据的内嵌设计规范；第 5 节以后为分阶段任务。执行前由用户确认本计划；跨阶段变更另行确认。

## 1. 依据、限制与纠正

- 基于上传的 backend.zip。已有约 226 个 test_ 函数只是静态统计，不是成功收集或通过数量。
- 前轮语法编译成功；pytest 缺失、附带依赖的 cryptography 初始化失败，不能宣称业务测试通过。
- 后端有增量事件 API，但没有前端源码，无法证明前端正在轮询，也不能确定轮询周期。
- Channels Consumer 已存在但 ASGI 路由被注释；Channel Layer 不是直接 WebSocket send_json 的必要条件。本计划引入 Redis Layer 是为了跨 Worker/API 进程通知，不是因为所有 WebSocket 都强制需要它。
- cmdb、automation、jobs、ops 在默认 settings 中未启用。不要逐个盲目取消注释：先检查模型导入和迁移依赖，再建立一个完整测试配置。
- jobs 已引用 automation 的版本/节点模型。本文的职责分离不等于反转 Python import 或 Django 迁移依赖。
- 用户明确要求直接重构、不保留历史实现，并说明本地已切换新分支；该分支尚未在本环境中验证。WorkerPool 直接归 jobs，所有外键和调用同步更新。

## 2. Global Constraints

- 本轮只实施用户批准的阶段；生产数据库、真实资产执行、凭据轮换和部署均需要单独授权。
- 允许删除本次重构范围内历史代码、旧接口、废弃模型和项目自有历史迁移文件；第三方迁移不得删除。新迁移只支持空库初始化，不支持旧数据库原地升级。
- 不要求旧 URL、字段别名、旧状态值和旧权限编码兼容；同步更新全部调用者、菜单、文档和测试，只保留一个正式契约。
- 不引入 Kafka、微服务、另一个工作流引擎或新的前端框架。
- 直接拆分职责混杂的 services/views，实现后删除被替代代码；禁止留下 legacy、compat、deprecated wrapper、旧代码注释备份和双轨开关。
- 本轮不直接指定未经验证的新依赖版本；先复现基线，再单独进行受支持版本升级与兼容验证。
- 不复制生产密码到测试，不输出秘密；新环境使用新密钥和新录入凭据，不实现旧密文兼容读取。
- 新分支不能隔离数据库、Redis 队列和日志目录。默认新建独立空数据库、独立队列前缀及日志目录，不连接旧库。清空任何已有数据库/存储必须确认环境和精确名称后另行授权。
- 不提供旧数据导入、回填、双写或历史作业恢复。这里删除的是历史实现；新系统仍必须保存新产生的执行历史和审计记录。
- 前端源文件路径必须从用户提供的 soybean-admin 实际仓库解析，不猜测目录并创建第二套页面。
- 工作目录若不是 Git 仓库，先确认真实仓库或交付方式；不擅自初始化仓库、提交或推送到外部。

## 3. 模块职责与删除策略

| 模块 | 负责 | 不负责 |
|---|---|---|
| audit_center | 操作者、动作、对象、结果、差异、关联执行 ID | 完整 stdout 和每个 Runner 事件 |
| cmdb | 资产、业务树、分组、标签、资产来源、凭据引用 | 作业状态机与 Worker 调度策略 |
| ops | inventory/playbook 构建适配、Runner 生命周期、取消、规范化回调 | 持有 WorkflowRun 状态或直接决定重试 |
| jobs | 运行实例、计划、状态机、队列、定时、重试、恢复、事件与投影 | 编辑工作流草稿 |
| automation | 命令/资源/工作流定义、版本、校验、发布 | 第二套运行实例与 DAG 调度器 |

依赖约定：jobs 读取 cmdb 资产和 automation 已发布定义，调用 ops 执行器；ops 核心接口不导入 jobs ORM。audit_center 提供显式记录入口，业务调用它。automation 如需触发运行，通过应用入口调用 jobs，避免模块初始化互相导入。

删除现有 ops/tasklog 文件轮询 Consumer、旧路由和 Celery 线程日志信号链；实时入口统一放到 jobs/realtime，输出归档统一放到 jobs/log_artifacts.py。需要保留的脱敏、ANSI 处理能力提取到新实现后删除原入口。ops/apps.py 删除旧 signal_handler 注册，将历史 ansible_platform app label 改为 ops，并更新所有模型引用及新迁移。

## 4. 运行与事件协议

### 4.1 执行计划

将 ExecutionPlan、RunnerResult、RunnerEvent 统一定义到 apps/ops/contracts.py，删除分散的重复类型和转发别名；所有调用方直接引用新位置。纯共享图协议位于 common/workflow，不导入 Django 模型。

- 计划包含 run_id、node_run_id、attempt 标识、目标快照、执行定义、超时、并发和必要运行参数。
- 目标快照包含稳定资产 ID、地址、端口、连接方式和凭据引用，不保存明文密码/私钥。
- 执行前重新验证资产与凭据使用权限；明确凭据策略为执行时读取有效版本，记录实际使用版本标识。没有凭据版本能力时记录引用和更新时间，不声称可完全重现旧凭据。
- Worker 实例 ID 不是资产 ID；WorkerPool 模型由 jobs 所有，cmdb 不再提供其模型或 API。
- 状态枚举在 jobs 统一定义，前端和序列化器同时改用新契约；删除旧状态映射，不改写旧数据库。

### 4.2 事件可靠性

- Runner callback 经脱敏后持久化 JobEventLog，并更新 HostRunResult/NodeRun 投影。
- 幂等键优先使用 run + node attempt + Runner 原生 event UUID；没有 UUID 的内部事件由生产者生成稳定 event_key，同一重试不能复用旧 attempt。
- event_id 用于标识，不默认认为数据库自增 ID 等于提交顺序。为运行流增加单调 sequence；分配 sequence 与事件写入在同一个持锁事务内完成。
- 新库初始化即建立运行内 sequence 唯一、运行内事件来源键唯一的约束。事件来源键包含 node/attempt 范围，工作流级事件使用明确的 run 范围，避免空 attempt 导致 SQL 唯一约束失效；无旧行回填。
- 事务提交后发送轻量通知；发送失败只记录监控和错误，不改变已提交的执行结果。
- 通知不是可靠队列。前端低频核对游标与终态，断线重连补拉。首期不做 Outbox；若未来要求通知本身必达，另行引入。
- 唯一事件接口返回升序 events、next_cursor、has_more、terminal 和 snapshot_version。删除旧 after_id 查询与旧响应结构，客户端全部使用 sequence 游标。
- 新订阅按 run 权限鉴权，客户端不自由指定 group；通知只包含 run ID 和最新 sequence，不推凭据/原始 inventory。
- 大量 stdout 不全部长期存 MySQL；结构化事件保留截断文本和归档引用，完整输出归档并通过鉴权下载。默认保留策略由管理员配置，首次上线不自动删除历史日志。

## 5. 执行纪律及阶段门槛

每项任务独立完成以下循环：

- [ ] 读取涉及源码与 AGENTS.md，核验目标分支，记录本任务目标契约和删除清单。
- [ ] 写本任务明确列出的回归用例。
- [ ] 执行单个用例，确认因目标行为缺失而失败，不把导入错误当有效红灯。
- [ ] 实施最小修改，执行本任务测试。
- [ ] 执行相关模块测试、全量回归和迁移检查。
- [ ] 检查 diff，确认没有秘密和无关删除；逐项核对被删代码的引用清零、新空库迁移可执行。
- [ ] 在真实仓库中形成单独本地提交，输出文件清单、命令、结果、剩余风险和回滚点；未经授权不推送。

阶段有失败即暂停晋级。新问题按既有缺陷、改造回归、环境故障分类，不修改断言来掩盖错误。

## 6. P0：可复现基线与安全前置

### T01 工作区、测试发现和依赖基线

文件：pyproject.toml、poetry.lock、conftest.py、devops/test_settings.py；新增 devops/test_full_settings.py、docs/testing.md；真实仓库的忽略规则。

输入：原始附件或用户指定的最新仓库。输出：完整测试清单、基础模式及全模块测试配置、可复现环境。

1. 核实 Python/Poetry/lock 内容与当前代码，不使用 .test-deps；保留原附件。
2. 检查 pytest 的 python_files：当前只有 test_*.py，应覆盖 tests.py 和 *_tests.py，避免大量测试被静默漏收集。
3. 基础 test_settings 保持隔离，完整测试配置按迁移依赖启用全部业务 app；SQLite 单测外增加隔离 MySQL 集成测试环境。
4. 记录 pytest --collect-only -q 的结果；检查目录名 tests.py 与新测试目录冲突，新测试采用 test_xxx.py 文件。
5. 先运行基线测试并分类失败；依赖下载受限时停报，不借用混装依赖继续声称可运行。

测试/命令：
```bash
poetry check
poetry run pytest --collect-only -q
poetry run pytest -q
poetry run python manage.py check --settings=devops.test_full_settings
poetry run python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings
```
验收：完整收集现有测试并记录失败原因；旧契约测试作为业务清单参考，不为保留旧接口而修复它们。新契约测试必须通过，删除旧测试须记录对应的新业务覆盖，不允许通过清空测试套件得到绿灯。

### T02 安全行为及生产配置

文件：devops/settings.py、apps/user/views/auth.py、common/auth/jwt.py、apps/permission/middleware.py、apps/cmdb/crypto.py；新增 apps/user/test_auth_security.py、apps/permission/test_log_redaction.py。

用例：query refresh token 不被接受；URL/body/header 中秘密不进日志；退出后 refresh 无效；禁用用户不能刷新；错误响应不泄露异常内部；不同来源访问遵守白名单。

措施：刷新只接收 body；统一脱敏；实现 refresh 吊销并明确 access 的失效窗口；生产缺失 Secret Key 时拒绝启动；开发与生产配置分离。新库使用新凭据密钥，不支持旧密文。CSRF 按 JWT、Session、admin 认证链路分别核验，不盲目关闭或开启后忽略回归。

依赖升级作为单独提交：根据执行时官方支持矩阵选定 Django/DRF/Channels/Celery/Python 组合，先测试再锁版本，不与模型搬迁同提交。

验收：安全用例通过；生产配置 check --deploy 的警告逐项解决或记载准确部署边界；没有访问生产服务。

## 7. P1：audit_center 标准流程

### T03 审计写入和只读查询

文件：apps/audit_center/{models,services,serializers,views,urls}.py、apps/audit_center/test_audit_contract.py、apps/permission/seeds 下实际相关种子文件。

输入：操作者、动作、对象、结果、关联 ID。输出：脱敏且可检索审计记录。

用例：普通用户无权读取他人范围审计；POST/PUT/PATCH/DELETE 审计记录被拒绝；筛选分页准确；密码和 token 被脱敏；导出权限独立校验；重复初始化菜单不产生重复条目。

操作：复用现有 create audit 服务；补足 request/run 关联字段；资源视图只读；保留明确的系统保留/清理通道但不暴露普通删除 API。审计关键动作采用显式调用，和普通 HTTP 访问日志分开。

前端：取得源码后选定现有用户/角色页面为唯一模式样板，记录 API、分页、搜索、弹窗、按钮权限与路由约定。audit 页面按样板改造，不替换布局组件。

验收：后端权限/序列化/种子测试通过；无前端源码时只签收后端，不声称 UI 验收完成。

## 8. P2：CMDB 资产契约

### T04 资产选择及非敏感快照

文件：apps/cmdb/{models,services,serializers,views}.py；新增 apps/cmdb/targets.py、apps/cmdb/test_targets.py；修改 apps/jobs/services.py 现有资产快照入口。

接口：resolve_targets(*, actor, host_ids, group_ids) -> list[dict]；snapshot_targets(*, actor, targets) -> list[dict]。快照统一使用 host_id、hostname、address、port、connection_type、credential_ref_id、variables；嵌套对象按统一 Schema 校验，不接收旧字段别名。同步更新 inventory 构建和前端资产选择调用者。

用例：多组主机去重；空/失效/无权限资产报明确信息；动态组过滤正确；修改 CMDB 不改变历史快照；快照不含密码/私钥；凭据停用后新执行拒绝。

操作：合并 jobs 内重复的资产解析；执行快照生成和权限验证集中处理；不靠浏览器传来的 inventory 作为可信目标。

### T05 WorkerPool 直接移入 jobs 与凭据解耦

文件：apps/cmdb/{models,views,serializers,urls,admin}.py、apps/jobs/{models,views,serializers,urls,admin,settings_service}.py、apps/ops/adapters.py；新增 apps/jobs/worker_pools.py、apps/jobs/test_worker_pools.py；更新权限和菜单种子。

接口：resolve_worker_pool(*, actor, pool_id, execution_kind) 返回 jobs.WorkerPool；queue_for_pool(pool) -> str。表名 jobs_worker_pool，API /api/v1/jobs/worker-pools；更新所有外键、import、管理后台、权限和前端。删除 cmdb WorkerPool 模型、旧 API 和别名。

用例：停用池拒绝；无权选池拒绝；队列选择和 worker 能力匹配；无在线 Worker 时结果是排队/告警而非伪成功；凭据只在执行端解密并清理临时文件。

验收：WorkerPool 仅在 jobs 中定义；旧 CMDB WorkerPool 路由返回 404；全量引用检查无旧模型路径；新空库初始化和队列选择测试通过。不提供历史 WorkerPool 数据搬迁。

## 9. P3：ops 执行器边界

### T06 唯一 Runner 合约与旧包装删除

文件：apps/ops/workflow/{adapters,ansible_service,events,inventory,playbooks}.py、apps/ops/services.py、apps/jobs/services.py；新增 apps/ops/workflow/test_execution_contract.py。

新增文件：apps/ops/contracts.py、apps/ops/executor.py。输入：统一 ExecutionPlan、事件回调、取消回调。输出：统一 RunnerResult 和 RunnerEvent。

用例：正常/失败/unreachable；超时；取消；无 callback 返回不能判为成功；未知事件保留安全元数据；no_log 内容不可见；清理仅限本次任务目录。

操作：统一 AnsibleExecutor.execute(plan, on_event, should_cancel) -> RunnerResult；jobs 负责资产解析与 ORM，ops 只执行计划。所有调用改用 execute，删除旧 Adapter.start、重复 Service 包装和多余事件类型。保留实际需要的底层 Runner 能力，不把删除历史实现误作删除 WinRM/网关业务支持。

### T07 隔离执行集成

文件：apps/ops/test_runner_integration.py、docs/runner-validation.md。

依次验证 fake runner、临时容器/明确授权测试主机、多主机、SSH 密钥、网关、WinRM。没有 Windows 测试目标时明确该项未验证，不能用 mock 通过替代生产兼容声明。

验收：至少一个真实隔离 Ansible 执行成功、一个失败、一个取消可复现；不连接附件中的生产地址。

## 10. P4：jobs 执行治理

### T08 提交与 Worker 领取

文件：apps/jobs/{tasks,services,state_machine,recovery}.py、apps/jobs/test_dispatch_contract.py；新增 apps/jobs/application/{__init__,runs,dispatch,cancel,retry}.py、apps/jobs/execution/{__init__,plan_builder,registry}.py。重构后所有调用直接引用职责模块，删除被替代的 services.py 入口，不保留转发壳。

用例：创建事务回滚不投递；投递失败留可恢复记录；重复投递只领取一次同一 attempt；重试产生新 attempt；恢复不盲目重跑可能有副作用的命令。

操作：沿用现有 ExecutionLease 和领取逻辑；任务在事务提交后投递；调度异常与执行异常区分；不得通过开启 Celery 自动重试来替代业务幂等。取消先记录 cancel_requested，再由 Runner 确认退出，不能收到 HTTP 200 就显示已取消。

### T09 事件序列、幂等与投影

文件：apps/jobs/{models,events,event_types,projections}.py、apps/jobs/test_event_delivery.py；新增独立迁移文件，序号由 makemigrations 实际生成。

新增概念：run 级事件 sequence、生产者 event_key、attempt 关联；复用现有字段优先，不盲目重复增加。

接口：append_run_event(*, run_id, node_run_id, attempt_id, event_key, event) -> JobEventLog。内部事件和 Runner 事件统一走入口，删除 persist_runner_event 和其他旁路写入入口；所有调用直接更新。

具体用例示例：
```python
@pytest.mark.django_db(transaction=True)
def test_duplicate_event_does_not_duplicate_projection(event_factory):
    first = event_factory.emit(event_key="runner-event-1")
    second = event_factory.emit(event_key="runner-event-1")
    assert first.pk == second.pk
    assert event_factory.logs().count() == 1
    assert event_factory.host_results().count() == 1
```
event_factory 在同文件 fixture 中使用真实 WorkflowRun/NodeRun/attempt 工厂创建合法记录，不向生产库写入。另测两个并发事务、乱序 callback、终态不回退、同 event_key 不同 attempt、死锁重试上限。

建库策略：在新分支重建项目自有迁移基线，以空 MySQL 库初始化；事件非空字段和唯一约束一次定义。不双写、不回填旧事件、不提供旧库升级命令；最终在 T15 再次从完全空库验证整个迁移图。

### T10 增量读取与实时通知

文件：apps/jobs/views.py、apps/jobs/urls.py；新增 apps/jobs/realtime/{__init__,publisher,consumer,routing}.py、apps/jobs/test_event_api.py、apps/jobs/test_realtime.py；修改 devops/asgi.py 和分环境 settings。

唯一事件接口：GET /api/v1/tasks/runs/{id}/events?cursor=0&limit=200，ops 域同形。删除 after_id 参数与其他重复事件读取 API；传入 after_id 返回参数错误，不静默忽略。limit 范围 1—1000，cursor 非负，严格按 sequence 排序。

响应示意：
```json
{"code":200,"data":{"events":[],"next_cursor":0,"has_more":false,"terminal":false,"snapshot_version":0}}
```
上例 code 仅示意；实际 code/message/http status 必须复用 common/api/responses.py，不硬编码改变现有 envelope。

唯一 WebSocket 路径 /ws/jobs/runs/，消息 subscribe 携带 run_id；响应 subscribed / events_available / error；事件数据由 REST 补拉。使用短期票据，票据一次性、绑定用户和运行、Redis 原子消费、过期 60 秒，日志脱敏并校验 Origin；删除旧 WebSocket 地址及 query JWT 鉴权。

用例：越权订阅拒绝；跨 run 数据不泄漏；未提交事务不通知；Redis 宕机任务仍完成；恢复后 REST 补齐；分页和重复通知不漏不重；没有 Channel Layer 时 HTTP 仍可查询。

重要：为避免 on_commit 通知失败反向污染业务结果，publisher 自行捕获传输异常并记录监控；Redis 不存唯一业务事实。

### T11 stdout 与归档

文件：apps/ops/tasklog/{consumer,logger,utils}.py、apps/jobs/serializers.py；新增 apps/jobs/log_artifacts.py、apps/jobs/test_log_artifacts.py。

操作：删除 ops/tasklog 整条文件轮询和 Celery 日志捕获信号链，删除对应 settings、apps.ready 注册和旧测试。新 Runner callback 输出经脱敏后通过 jobs/log_artifacts.py 归档，接口鉴权下载，受控路径、大小限制、分块读取，不暴露服务器路径。多 Worker 部署验证共享归档存储可达，不假设本地磁盘共享。

用例：路径穿越拒绝；跨任务下载拒绝；大文件内存有界；ANSI/UTF-8 分块不损坏；no_log 脱敏；任务失败仍能下载已有输出。

## 11. P5：automation 定义与运行隔离

### T12 图协议集中与不可变版本

文件：apps/automation/{workflow_graph,models,serializers,views}.py、apps/jobs/{workflow_engine,node_executors,services}.py；新增 common/workflow/{__init__,schema,node_types,conditions}.py、apps/automation/test_published_contract.py。

输入：现有图结构、节点定义、资源版本。输出：校验后的已发布图和运行快照。

操作：将共享节点常量和纯校验集中到 common/workflow，删除旧定义和 import 别名；编辑期校验在 automation，运行期调度只在 jobs。发布冻结节点、边及命令/资源版本；只有图 hash 不等于完整可重现。

用例：已发布版本不可原地修改；修改草稿不改变运行；非法环/悬空边/未知节点拒绝；合法分支与汇合可运行；删除模板不破坏新系统已有运行；不支持的旧 editorMode、旧图结构必须明确拒绝，不自动转换。

### T13 执行入口收敛

文件：apps/automation/views.py、apps/jobs/{services,views,workflow_engine}.py、apps/jobs/test_execution_entrypoints.py。

操作：快捷命令、手工作业、工作流、定时任务均进入同一运行创建/调度服务，execution_kind/run_domain 区分展示和策略；API/Jenkins/通知执行器继续使用现有实现，不因 ops 专注 Ansible 而强行搬迁。

用例：不同入口产生同一种可查询运行记录；取消/重试统一；Jenkins/API 外呼 mock 覆盖超时、重定向目标验证和凭据脱敏；不调用真实 Jenkins 构建或通知收件人。

## 12. P6：前后端闭环与交付

### T14 前端契约和页面改造

输入前提：用户提供实际 soybean-admin 前端源码。未提供时该任务阻塞，后端阶段可以独立推进。

具体操作：读取 package.json、路由生成方式、API 封装、类型定义及标准页面；生成真实文件清单后再编辑。保持 soybean-admin 框架、主题和组件规范；按新契约重构 API/types/页面/菜单，删除旧请求方法、字段映射、旧日志连接和废弃页面，不做双版本适配。

同步流程：REST 取快照及游标→订阅→立即补拉消除窗口→收到通知按序补拉→按 sequence 去重→断线退避重连→低频 REST 校对→终态最后补拉再停轮询。切换任务/卸载页面时取消请求和订阅，旧请求不得写入新任务页面。

验收：审计列表、资产选择、执行创建、节点状态、主机结果、日志、取消、重试全部联调；浏览器刷新和断线恢复不丢事件；页面按钮权限与 API 权限一致。

### T15 集成、性能和灰度

文件：docs/deployment.md、docs/rollback.md、docs/acceptance.md；部署配置按用户实际 Docker/systemd/Kubernetes 方式新增，不同时引入三套。

验证：隔离 MySQL + Redis + Worker + ASGI 服务；2 个 Worker 与 2 个 API 实例下执行/订阅；终止 Worker、断开 Redis、断开浏览器、重复事件、多并发消费者场景。

性能起点：使用合成事件测试 10 个运行、20 个订阅者、总计 100 events/s 持续 10 分钟；核对无漏事件、内存不持续增长，并记录硬件、P95 延迟、DB 锁等待。该值是首轮测试负载，不是生产容量承诺；正式 SLO 按实际规模确认。

上线步骤：独立新数据库/Redis 命名空间/归档目录→空库初始化→新权限种子→配套前后端及 Worker 验证→用户授权切换→观察错误率和延迟。禁止新旧 Worker 消费同一队列；本计划不部署兼容代码、不对旧库执行迁移。

回滚：WebSocket 故障退回新协议 REST，不属于旧实现兼容。整体回退必须同时切换配套代码、配置、数据库和队列；新库不可直接交给旧代码使用。若旧环境已被用户授权销毁，只能从备份重建；Git 分支不能恢复数据库。新系统产生的数据不自动反向迁回旧环境。

## 13. 每阶段交付格式

- 阶段/任务编号及完成、未完成项。
- 修改文件和每项修改理由。
- 新接口、字段、迁移、配置及破坏性变化；被删除文件/符号/路由与业务替代去向。
- 实际测试命令、收集数、通过数、失败数和未运行项。
- 外部依赖/权限阻塞，不能用 mock 结果冒充真实集成通过。
- 风险、回滚方式、下一阶段入口。

## 14. 总验收清单

- [ ] 基础和完整业务配置均能启动，测试无漏收集。
- [ ] MySQL 迁移、并发序列和幂等测试通过。
- [ ] 审计不可由普通 API 修改，秘密不进入日志或快照。
- [ ] CMDB 修改不改变运行目标快照。
- [ ] ops 核心执行不依赖 jobs ORM，ops/tasklog 和旧日志地址已删除。
- [ ] WorkerPool 仅归 jobs，无 CMDB 旧模型、路由和 import 别名。
- [ ] 项目自有迁移从空库可完整执行，无历史回填、双写或兼容迁移。
- [ ] 无旧接口调用、旧权限种子、废弃文档和未使用依赖；删除清单逐项验收。
- [ ] 一个运行只有一套状态机，所有入口统一治理。
- [ ] 断线、重复通知、Redis 故障不丢最终执行记录。
- [ ] automation 发布定义与运行快照隔离。
- [ ] 前端保持 soybean-admin 既有页面规范。
- [ ] 多实例、真实隔离 Runner、灰度和恢复演练有证据。

## 15. 执行起点

执行从 P0/T01 开始：核验用户新分支和最新源码，建立删除清单、独立新数据库配置与全模块测试配置。然后依次 audit_center → cmdb/WorkerPool → ops → jobs/实时事件 → automation → 前端联调。直接重构不等于跳过阶段验证；无旧代码兼容要求，也不要求先修复所有旧契约测试。前端源码和真实测试环境仍须用户提供；本轮仅修改计划，尚未开始源码删除或数据库操作。

## 16. 历史清理与迁移重建任务（跨阶段执行）

- [ ] T01 记录 git status、分支、基准提交及所有项目自有迁移依赖；检查新分支是否与旧分支共享数据库/队列。
- [ ] T05 删除 CMDB WorkerPool 定义及调用；新 jobs 模型和所有相关外键一次更新。
- [ ] T06 删除重复执行入口；T08 删除已拆分服务的旧导出；T09 删除事件旁路写入。
- [ ] T10/T11 删除旧 WS、旧游标、日志信号处理器及依赖；T12 删除旧图格式和控制节点语义分支。
- [ ] 模型归属确定后重建项目自有 apps 的迁移文件，保留 __init__.py；第三方迁移不动。用户/权限/审计的跨 app 外键也要纳入完整依赖图，不能单独删除某个 app 迁移而留下悬空依赖。
- [ ] 循环外键由 Django 拆为初始建表与后续加外键迁移；不强求每个 app 只有一个 0001。种子数据使用唯一的幂等初始化命令，不保留旧菜单迁移脚本。
- [ ] 用全新、明确授权的空库执行 migrate、初始化权限、创建测试用户、再运行集成测试；已有 django_migrations 表的旧库拒绝作为新基线目标，不使用 --fake 掩盖差异。
- [ ] 删除清单使用具体文件/符号，不按 legacy/old 字符串机械批量删除；每项保留有效业务测试或给出业务能力废弃说明。
- [ ] 最终全库检索旧路径、旧类名和旧路由；剩余命中只能是明确断言旧入口不可用的负向测试或删除验收文档。
- [ ] 清理源码包中的 .test-deps、缓存和生成文件时先确认精确目录；不删除用户原附件、无关文件或运行数据。源码删除由 Git 恢复，缓存可重新生成；数据删除不在本次计划修改操作内。
