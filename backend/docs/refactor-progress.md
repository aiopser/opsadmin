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
