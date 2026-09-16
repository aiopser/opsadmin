# 增量事件与实时通知

唯一 REST 事件入口为 `/api/v1/tasks/runs/{id}/events`，ops 域为 `/api/v1/ops/runs/{id}/events`。参数 `cursor` 默认 0、非负；`limit` 默认 200、范围 1—1000；`after_id` 明确返回 400。响应沿用 code/data/msg envelope，data 为 events、nextCursor、hasMore、terminal、snapshotVersion。只返回当前快照序号以内的事件，消费者按 sequence 续读并去重。无 Channel Layer 时 REST 仍可用。

WebSocket 唯一路径 `/ws/jobs/runs/`，不接受 query token。先通过已登录 HTTP 会话 POST 同一 run 的 `realtime-ticket` 子资源，获取 ticket 和 expires_in=60。随后向 WS 发送 `{ "type": "subscribe", "run_id": 123, "ticket": "..." }`。服务器返回 subscribed、events_available 或 error；通知只含 run_id/sequence，不携带事件数据，收到通知后使用 REST 补拉。普通用户只访问本人运行，超管按已有 RBAC 访问；票据消费后重新检查用户状态和资源权限。

通知按 run 合并（2026-09-14）：事件密集时（压测 50+ eps）逐条 group_send 会压垮 channel layer 并造成通知积压丢失，因此通知降级为「有新事件，请补拉」的提示语义——前沿立即发一条，1 秒窗口内后续事件静默，静默结束后补发最新 sequence 一条（Redis `cache.add` NX 全局限流，进程内 trailing Timer 保证尾部必达；缓存故障退化为逐条通知）。消费者不得假设「每条事件恰好一条通知」，数据完整性以 REST 游标补拉为准：只要收到任意一条通知或轮询触发，即可从上次 cursor 拉到全部新事件。发送侧使用进程级常驻事件循环执行 group_send，避免发布线程串行排队；WS 消费端的权限复核加 5 秒 TTL 缓存（订阅时已完整鉴权，TTL 到期后复核失败即断开 4403）。

事件 sequence 分配不再对 run 行全程加锁（2026-09-14）：`append_run_event` 无锁读 run，sequence 由 `(workflow_run, sequence)` 唯一约束兜底并发分配（冲突顺延重试，event_key 冲突返回既有事件保持幂等），`run.event_sequence` 以 `Greatest` 原子单调推进，REST 上界 `sequence__lte=run.event_sequence` 始终覆盖已提交事件。原实现单 run 事件吞吐受 `select_for_update` 串行化限制（约 5 eps），去锁化后并发 worker 可同时向同一 run 追加事件。

部署时显式配置 `DEVOPS_REALTIME_REDIS_URL` 和逗号分隔的 `DEVOPS_REALTIME_ALLOWED_ORIGINS`。未配置 Redis 时不会推导任何生产连接，票据接口返回 503，REST 保持可用；未配置 Origin 白名单时 WS 拒绝握手。票据仅在 Redis 存储哈希键，TTL 60 秒，Lua GET+DEL 原子消费，绑定 user/run，单次有效。Broker/Channel 通知错误只记录异常类别，不反向修改运行结果。

T10 已验证：SQLite + 内存 Channel Layer + fake Redis 的分页、越权、票据单次/过期、Origin/query JWT 拒绝、跨 run 通知隔离、事务回滚不通知、传输异常后事件仍持久化。真实 Redis Lua 并发、多 ASGI 实例断线重连尚未验证，不把 fake Redis 结果视为真实集成通过。
