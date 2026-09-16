# 第 4 节验收结果：性能压测

- 结论：**FAIL（按"通知三方一致"标准）；数据层完整性 100%；不给出容量结论**
- 日期：2026-09-09（负载时长按用户要求压缩为 120s，原计划 600s）
- 执行人：内网 Agent（192.168.12.26）

> **口径修订（2026-09-14）**：本报告 FAIL 依据的「消费者收到的唯一 sequence 数 = 发送数」标准基于旧的逐条通知语义。此后通知协议改为按 run 合并（前沿+静默尾部补发，见 `docs/realtime-events.md`），WS 通知不再是逐事件保证，而是补拉提示；完整性口径相应改为「消费者经通知+REST 游标补拉后获得的事件 sequence 并集 = 发送数」。据此，本报告「通知丢失」项按新口径不成立（REST 补拉兜底已验证发布→补拉 P95 2.5s、数据最终一致），「21s 通知长尾」已由合并+独立事件循环发送修复（待复测）。**根因 1（单 run 吞吐 ~5 eps 的 run 行锁串行化）已于 2026-09-14 实施去锁化修复（唯一约束兜底并发分配 sequence），待复测验证。**

## 压测前环境记录（验收要求项）

| 项 | 值 |
| --- | --- |
| 主机 | lojenkins，CentOS 7 (3.10.0-1160.el7)，8 核，15867MB 内存，/opt 399G（用 7%） |
| Python | 3.12.10 |
| 关键包 | Django 5.2.17、channels 4.3.2、channels-redis 4.3.0、daphne 4.2.3、celery 5.6.3、ansible-runner 2.4.3、redis-py 4.6.0 |
| API/ASGI | 2x daphne（8101/8102） |
| Worker | 2x（w1@acc/w2@acc，concurrency=4，队列 acceptance.worker,task,ops） |
| Redis | 5.0.5（192.168.12.107，realtime=db6，broker=db7；maxmemory≈4GB） |
| MySQL | 8.0.46（192.168.12.107，test_devops_acceptance；max_connections=500，buffer pool 4GB） |
| 数据库连接 | CONN_MAX_AGE 未显式设置（验收 settings 继承开发配置） |
| 归档存储 | 本地磁盘 FileSystemStorage（/opt/devops_platform/acceptance/job-logs，单块 16MB） |

## 负载参数

- 10 个真实 quick command 运行（run 46-55，全部 success，真实 ansible runner 执行）
- 20 个 WS 订阅者（10 runs × 2，均匀分布两个 API 实例，全程 0 断连）
- 事件负载：与 Worker 相同的 `append_run_event` 管道注入，目标 100 events/s，实际 **51.8 events/s**（受发布端吞吐上限约束，见根因）
- 持续 120s + 90s 排空窗口

## 结果指标

| 指标 | 值 | 判定 |
| --- | --- | --- |
| 发送事件数 = 持久化事件数 | 6220 = 6220，缺失 0、重复 0 | ✅ |
| 消费者收到的唯一 sequence | 每订阅者缺 ~5%（620 条中缺约 30-50 条） | ❌ 通知不完整 |
| 通知 → REST 补拉 P95 | 负值（REST 1s 轮询常先于 WS 通知到达）→ 该口径无意义，改用发布→补拉 | 记录 |
| 发布 → 通知 P95 | 21.482s | ❌ 通知路径严重积压 |
| 发布 → REST 补拉 P95 | 2.521s | 记录 |
| 内存 | daphne 111→146MB / 99→108MB；worker 恒定 462/467MB；Redis 5.4→5.5MB；无持续增长 | ✅ |
| MySQL 锁等待 | Innodb_row_lock_waits +934（均值 48ms，共享实例计数为上界）；无死锁计数项 | 记录 |
| 断连 | 0 | ✅ |

## 根因分析

1. **单 run 事件吞吐 ~5 eps（append 串行化）**：`append_run_event` 对 run 行 `select_for_update` + `event_sequence` 自增，同一 run 的事件追加完全串行，单条约 190ms；10 并发 run 理论上限 ≈ 52 eps，与实测 51.8 吻合。**100 eps 目标在当前实现下无法通过 10 个 run 达成**（需 ~20 并发 run 或优化事件序列分配）。
2. **通知丢失与 21s 长尾**：`publish_events_available` 经 `async_to_sync(group_send)`（默认 thread-sensitive）在多发布线程间串行排队；且 Redis pub/sub 无 backlog，daphne 端 `events_available` 每条通知触发 `still_authorized()` 数据库查询，消费不及时即丢弃。前端已有 REST 轮询兜底（发布→补拉 P95 仅 2.5s，数据最终一致），但按验收标准"消费者收到的唯一 sequence 数 = 发送数"不达标。

## 优化建议（供后续迭代，不构成本次验收结论）

- 事件序列分配去 run 行锁化（如 Redis INCR per run 或唯一约束 + 重试）。
- `group_send` 改用独立 event loop / `thread_sensitive=False`，避免发布线程串行化。
- `RunEventsConsumer.events_available` 的鉴权查询加短 TTL 缓存（订阅时已验证过）。

## 跳过项及原因

- 600s 满时长压测：按用户指示压缩为 120s；长时内存漂移观测样本相应减少（13 个采样点）。

## 失败时的回滚动作

- 压测为只读负载 + 隔离库写入，无需回滚；拓扑实例未受影响（压测后 2 API + 2 Worker 健康）。

## 是否访问过生产资产

- 否。全部流量在隔离库/队列/回环资产上；MySQL/Redis 计数器因共享实例仅作上界参考。

## 原始数据

- `perf_summary.json`：汇总与环境记录
- `perf_samples.json`：每 10s 资源采样序列（RSS/Redis/MySQL）
- 内网原始日志：192.168.12.26:/opt/devops_platform/acceptance/results/perf.log
