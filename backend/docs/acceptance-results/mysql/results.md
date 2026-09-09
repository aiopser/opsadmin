# 第 1 节验收结果：MySQL 真实迁移、并发序列、锁和幂等

执行日期：2026-09-09
执行环境：本机 Windows + 本机 MySQL80 服务（用户指定 10.0.0.40:3306，实测经 127.0.0.1:3306 同一实例）
未访问任何生产资产；未使用旧库；未使用 --fake。

## 环境

- MySQL 版本：8.0.46（Community）
- 隔离级别：REPEATABLE-READ（默认，未改）
- 测试库：`test_devops_mysql_acceptance`（全新空库，`CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`）
- Python：3.12（backend/.venv），驱动 pymysql 2.2.8（devops/__init__.py 注册 MySQLdb shim）
- 驱动差异说明：未使用 mysqlclient；Django 经 pymysql shim 连接。

## 设置扩展（本次为连接本机 MySQL80 所需）

`devops/test_mysql_settings.py` 新增两个显式环境变量（默认行为不变）：

- `DEVOPS_TEST_MYSQL_HOST`：覆盖 HOST（默认仍 127.0.0.1）。
- `DEVOPS_TEST_MYSQL_ALLOW_DEFAULT_PORT=yes`：显式豁免 3306 端口保护（用于本机已有实例；容器方案仍应使用专用端口）。
- `DEVOPS_TEST_MYSQL_DB_SUFFIX`：固定库名后缀，保证 migrate 与 pytest 指向同一库，便于复现。

## 实际命令

```powershell
# 建全新空库（先 DROP 保证空库）
& .\.venv\Scripts\python.exe -c "import pymysql; c=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='<隔离密码>'); cur=c.cursor(); cur.execute('DROP DATABASE IF EXISTS test_devops_mysql_acceptance'); cur.execute('CREATE DATABASE test_devops_mysql_acceptance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); c.close()"

$env:DEVOPS_TEST_MYSQL_ISOLATED="yes"
$env:DEVOPS_TEST_MYSQL_PORT="3306"
$env:DEVOPS_TEST_MYSQL_ALLOW_DEFAULT_PORT="yes"
$env:DEVOPS_TEST_MYSQL_USER="root"
$env:DEVOPS_TEST_MYSQL_PASSWORD="<隔离密码>"
$env:DEVOPS_TEST_MYSQL_DB_SUFFIX="mysql_acceptance"

.\.venv\Scripts\python.exe manage.py migrate --settings=devops.test_mysql_settings   # 全部 OK
.\.venv\Scripts\python.exe manage.py check   --settings=devops.test_mysql_settings  # no issues (0 silenced)
.\.venv\Scripts\python.exe -m pytest apps/jobs/test_event_api.py apps/jobs/test_event_delivery.py apps/jobs/test_execution_entrypoints.py --ds=devops.test_mysql_settings --basetemp=.pytest_cache/mysql-acceptance -q
```

## 结果

- migrate：43 个迁移在空库全部应用成功，无失败；二次运行 0 待应用（幂等确认）。
- check：System check identified no issues (0 silenced)。
- pytest：**37 passed in 28.61s**（test_event_api + test_event_delivery + test_execution_entrypoints）。

## 验收点核对

| 验收点 | 结果 | 证据 |
| --- | --- | --- |
| 并发 producer 对同一 run 写事件 sequence 连续且不重复 | PASS | `test_two_mysql_transactions_allocate_unique_sequences`（ThreadPoolExecutor 2 workers + Barrier 同步，真实 MySQL 事务，通过） |
| 相同 event_key 重复提交只产生一个事件 | PASS | `test_duplicate_event_does_not_duplicate_projection`、`test_database_rejects_duplicate_sequence_and_event_key` |
| 不同 node/attempt 相同事件 key 不互相冲突 | PASS | `test_same_key_in_new_attempt_is_independent` |
| MySQL 1205/1213 锁冲突按设计重试，超过上限明确失败 | PASS | `test_deadlock_retry_is_bounded`（模拟 1213）；实现见 `apps/jobs/events.py:277`，重试上限 2 次后明确抛出 |
| 空库完整迁移图 | PASS | 43 个迁移全部应用 |
| 数据库版本/隔离级别/并发数 | 已记录 | MySQL 8.0.46 / REPEATABLE-READ / 并发 2 producer |

## 限制与待内网补充项

- 本机实例非容器专用端口（用户指定的既有 10.0.0.40:3306 实例），已通过 `DEVOPS_TEST_MYSQL_ALLOW_DEFAULT_PORT=yes` 显式豁免；内网若用容器方案仍应遵循专用端口约束。
- 未单独记录 `innodb_lock_wait` 等锁等待指标（37 个用例运行期间无锁等待告警输出）；如需量化锁等待统计，在第 4 节压测中记录。
- 并发数 2（测试内建）；更高并发（如 8/16 producer）属于第 4 节压测范围。

## 清理

测试库保留供复查：`DROP DATABASE IF EXISTS test_devops_mysql_acceptance;`
