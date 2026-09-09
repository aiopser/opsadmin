# 增量事件与实时通知

唯一 REST 事件入口为 `/api/v1/tasks/runs/{id}/events`，ops 域为 `/api/v1/ops/runs/{id}/events`。参数 `cursor` 默认 0、非负；`limit` 默认 200、范围 1—1000；`after_id` 明确返回 400。响应沿用 code/data/msg envelope，data 为 events、nextCursor、hasMore、terminal、snapshotVersion。只返回当前快照序号以内的事件，消费者按 sequence 续读并去重。无 Channel Layer 时 REST 仍可用。

WebSocket 唯一路径 `/ws/jobs/runs/`，不接受 query token。先通过已登录 HTTP 会话 POST 同一 run 的 `realtime-ticket` 子资源，获取 ticket 和 expires_in=60。随后向 WS 发送 `{ "type": "subscribe", "run_id": 123, "ticket": "..." }`。服务器返回 subscribed、events_available 或 error；通知只含 run_id/sequence，不携带事件数据，收到通知后使用 REST 补拉。普通用户只访问本人运行，超管按已有 RBAC 访问；票据消费后重新检查用户状态和资源权限。

部署时显式配置 `DEVOPS_REALTIME_REDIS_URL` 和逗号分隔的 `DEVOPS_REALTIME_ALLOWED_ORIGINS`。未配置 Redis 时不会推导任何生产连接，票据接口返回 503，REST 保持可用；未配置 Origin 白名单时 WS 拒绝握手。票据仅在 Redis 存储哈希键，TTL 60 秒，Lua GET+DEL 原子消费，绑定 user/run，单次有效。Broker/Channel 通知错误只记录异常类别，不反向修改运行结果。

T10 已验证：SQLite + 内存 Channel Layer + fake Redis 的分页、越权、票据单次/过期、Origin/query JWT 拒绝、跨 run 通知隔离、事务回滚不通知、传输异常后事件仍持久化。真实 Redis Lua 并发、多 ASGI 实例断线重连尚未验证，不把 fake Redis 结果视为真实集成通过。
