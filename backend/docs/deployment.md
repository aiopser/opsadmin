# V2 独立环境交付

状态：尚未执行部署。实际 Docker/systemd/Kubernetes 托管方式未确认，本阶段不生成未经核验的部署配置。

## 切换前提

使用独立新 MySQL 数据库、独立 Redis 实例或经过核验的命名空间、独立队列和归档目录。不得对已有数据库运行本分支迁移，不得让新旧 Worker 消费同一队列。数据库账号只授予新环境所需权限。

Web、ASGI、调度进程、Linux Worker 和前端必须使用同一发布版本。根据实际 WorkerPool 的 queue_name 配置消费者；运行前核对池的启用状态与支持的执行类型。不得用默认配置探测生产连接。

## 初始化顺序

1. 人工核对实际配置中的数据库、Broker、缓存、Channel Layer、归档目录和资产地址全部属于隔离环境。
2. 在独立空 MySQL 库验证完整迁移图，然后初始化当前权限和菜单种子。当前迁移仅支持新空库，详见 migration-baseline.md。
3. 配置凭据加密密钥，确保各服务一致；凭据只以引用进入运行快照。
4. 配置 DEVOPS_REALTIME_REDIS_URL 和 DEVOPS_REALTIME_ALLOWED_ORIGINS；Origin 必须对应实际前端。缺少实时 Redis 时票据接口返回 503，事件 REST 仍可读取。
5. 配置 DEVOPS_LOG_ROOT 和 DEVOPS_LOG_MAX_BYTES。多个 API/Worker 必须共享 job_logs 存储，详见 log-artifacts.md。
6. 启动配套服务，在明确授权的隔离资产上完成 acceptance.md 中真实集成项目。
7. 保存版本、配置摘要、测试报告和回滚位置，获得用户切换授权后再切换入口。观察错误率、事件延迟、队列积压和归档失败。

本地 SQLite、模拟接口及内存 Channel Layer 的结果不能替代以上交付门槛。
