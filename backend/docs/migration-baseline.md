# V2 新空库迁移基线

2026-09-08 按 V2 直接重构方案，移除项目自有 80 个历史迁移源文件，以 Django 5.2.17 `makemigrations --settings=devops.test_full_settings --noinput` 实际生成新的 initial 迁移图。包含 user、permission、audit_center、cmdb、automation、jobs；ops 不再使用历史 ansible_platform label，没有自有模型迁移。第三方 Django 和 SimpleJWT blacklist 迁移未改动。

此迁移图只用于新空库。它不包含旧库升级、历史 WorkerPool 搬迁、事件回填或旧表清理步骤。不要对已有部署数据库执行这些迁移；本次没有连接或清空任何已有数据库。

新事件表一次定义 run/sequence 和 run/event_key 唯一约束。producer event_key 按 node/attempt 命名空间存储；HostRunResult 是当前 attempt 的投影，日志保留每次 attempt 的事件。事件入口锁定 run 分配连续 sequence，同一事务写入日志和投影；重复事件返回原记录。仅对 MySQL 1205/1213 错误重试，最多三次。

SQLite 内存测试数据库已成功从新迁移图建库。MySQL 并发事务测试仅能使用 devops.test_mysql_settings 的明确隔离实例配置；默认 SQLite 下会明确 skipped，不能作为 MySQL 锁行为通过证据。真实 MySQL 空库初始化仍待可用的隔离实例。

历史迁移中的数据迁移和隐式种子已删除。初始化应用配置应使用当前管理命令及明确的新环境启动流程；不得重新导入旧数据迁移来制造测试默认数据。
