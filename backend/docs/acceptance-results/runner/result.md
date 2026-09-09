# 第 3 节验收结果：真实隔离 Runner、灰度和恢复演练

- 结论：**7/7 PASS**
- 日期：2026-09-09
- 执行人：内网 Agent（192.168.12.26）

## 环境和拓扑

- Runner：ansible-runner 2.4.3（真实 SSH，目标为本机回环授权隔离资产 acc-target-local 127.0.0.1）
- 2x daphne API（8101/8102）+ 2x Worker（w1@acc/w2@acc，真实 runner 模式）
- 灰度 Worker：canary@acc（仅消费 acceptance.canary 队列）
- 隔离边界：不使用生产主机/凭据/网关/队列；无资产自动发现

## 实际命令

```bash
source /opt/devops_platform/acceptance/scripts/env.sh
cd /opt/devops_platform/backend && source venv/bin/activate
python /opt/devops_platform/acceptance/scripts/s3_scenarios.py
```

## 场景结果（run ID / 状态变化 / 关键校验）

| 场景 | 结果 | 关键数据 |
| --- | --- | --- |
| S1 Linux SSH 成功执行 | PASS | run=38 success，node rc=0，host result rc=0，stdout 含标记 |
| S2 命令失败落库且秘密不进日志 | PASS | run=39 failed；host rc=42；`password=[REDACTED]` 脱敏生效；秘密未出现在事件与日志归档 |
| S3 运行中取消 | PASS | run=40 观测到 cancel_requested → canceled 两阶段；节点 canceled |
| S4 Worker 执行中终止 + 恢复扫描 | PASS | run=41：SIGKILL 双 Worker（14:48:42）→ 扫描（14:49:19）recovered=1 → status=timeout，reason=heartbeat expired；副作用标记文件恰好 1 行、attempts=1（无重复执行）；Worker 已恢复 |
| S5 Redis 短暂中断 | PASS | CLIENT PAUSE 3s 期间 REST 事件读取 0.10s 完成；触发延迟 3.21s 后自动恢复；run=42 success，事件序列连续 |
| S6 断开重连按 cursor 补齐 | PASS | run=43：在线收 [15,16]，断线期间 [17,18,19] 经 REST cursor 补齐无缺失，重订阅后 [20] 通知恢复 |
| S7 灰度队列隔离 | PASS | canary run=44 由 canary@acc 执行；旧池 run=45 由 w2@acc 执行；dashboard health 队列映射 acceptance.worker→[w1,w2]、acceptance.canary→[canary] 不相交 |

## 过程中发现并修复的产品缺陷

1. **Quick command `timeoutSeconds` 契约缺口**：`QuickCommandRunCreateSerializer` 接受并校验 `timeoutSeconds`，但 `create_quick_command_run` 未传递，导致 run 级超时静默丢失（S4 首轮失败根因）。已修复 `apps/jobs/serializers.py` 与 `apps/jobs/application/runs.py` 传递链路并回归通过。
2. 节点级 `exit_code` 为 ansible-runner 进程 rc（失败 play 恒为 2），命令真实退出码记录于 host 结果 `rc` 字段——行为符合设计，已在验收断言中区分。

## 失败时的回滚动作

- 首轮 S2/S4 失败均为断言口径或契约缺口，修复后全量重跑通过；无数据回滚需求。
- S4/S7 场景结束均自动恢复被停实例（api-two/worker-w2/worker-canary）。

## 是否访问过生产资产

- 否。仅本机回环 SSH 自连接（授权测试资产）与隔离队列/库。
