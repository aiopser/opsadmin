# 第 2 节验收结果：多实例 API/ASGI、Worker、共享归档

- 结论：**7/7 PASS**
- 日期：2026-09-09
- 执行人：内网 Agent（192.168.12.26）

## 环境和拓扑

- 2x daphne API：http://127.0.0.1:8101、http://127.0.0.1:8102
- 2x Celery Worker：w1@acc、w2@acc（-Q acceptance.worker,task,ops，concurrency=4）
- MySQL：test_devops_acceptance@192.168.12.107:3306（隔离空库）
- Redis：192.168.12.107 db5(cache)/db6(realtime)/db7(broker)/db8(result)
- 日志归档：/opt/devops_platform/acceptance/job-logs

## 实际命令

```bash
source /opt/devops_platform/acceptance/scripts/env.sh
cd /opt/devops_platform/backend && source venv/bin/activate
python /opt/devops_platform/acceptance/scripts/s2_scenarios.py
```

## 场景结果（run ID / 校验值）

| 场景 | 结果 | 关键数据 |
| --- | --- | --- |
| S1 多节点运行仅一套记录 | PASS | run=23 success；4 节点；nodeA/nodeB 各 1 attempt；运行列表出现 1 次 |
| S2 两 Worker 竞争仅一个 attempt 被领取 | PASS | node 71/72 attempt_count=1 |
| S3 两 ASGI 实例订阅者按 sequence 收到通知 | PASS | 两订阅者均收到 seq=[15,16,17]，完全一致 |
| S4 重复投递/提交 REST 只保留一份 | PASS | 重复 event_key 仅 1 条（sequence=18） |
| S5 多 Worker 并发写归档不互相覆盖 | PASS | 3 并发运行全 success；29 个 chunk 文件；3/3 标记完整 |
| S6 两实例日志一致 + 权限正确 | PASS | sha256 前 12 位=575796f6f9b9 相同；匿名 401；viewer 403 |
| S7 停任一 API/Worker 后最终状态仍落库 | PASS | 停 api2 后 run=28 success；停 w2 后 run=29 success；实例已恢复 |

完整数据见 `s2_summary.json`。

## 过程中发现并修复的问题

1. `apps/jobs/tasks.py` 死锁重试函数缺失 `import time` 与 `OperationalError` 导入（本地修复后同步内网）。
2. 验收脚本 S2 场景读取了错误字段名（`attemptCount` → 实际契约 `attempt_count`）；S3 场景订阅了错误的 run 且消息类型断言错误（应为 `events_available`）——均为测试脚本缺陷，后端行为正确。
3. S7 场景结束后未恢复被停实例，导致脚本不可重复执行——已补充自动恢复逻辑。

## 失败时的回滚动作

- 无失败项。场景脚本全部幂等可重复执行。

## 是否访问过生产资产

- 否。仅使用隔离库 test_devops_acceptance、Redis db5-8、专属队列 acceptance.worker 与本机回环目标主机。
