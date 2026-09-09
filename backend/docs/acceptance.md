# V2 验收记录

当前尚未达到整体交付验收。测试均未连接生产资产或清空已有数据库。

2026-09-09：第 1 节（隔离 MySQL 迁移/并发/幂等）与第 5 节（生产配置静态检查）已在本机完成。多实例拓扑（第 2 节）、真实 Runner（第 3 节）、性能压测（第 4 节）仍需内网环境，保持“环境阻塞/未验收”状态，不以本地模拟结果替代。

## 已执行

- 2026-09-09 第 1 节隔离 MySQL 验收（本机 MySQL 8.0.46 空库 `test_devops_mysql_acceptance`）：migrate 43 个迁移全部应用、check 无问题、事件/并发/幂等 pytest 37 passed（28.61s）。详见 [acceptance-results/mysql/results.md](acceptance-results/mysql/results.md)。
- 2026-09-09 第 5 节生产配置静态检查：强密钥/ALLOWED_HOSTS/CREDENTIAL_KEY 拒绝行为实测 PASS；发现并修复 `frontend/.env.prod` mock 地址残留（改为占位符 + TODO）。未访问生产资产。详见 [acceptance-results/production-static/results.md](acceptance-results/production-static/results.md)。
- T13/T14 当前完整后端回归：370 passed、4 skipped、17 subtests passed；4 skipped 为真实 Runner 3 项与 MySQL 并发 1 项。
- 2026-09-09 权限回归：`python -m pytest apps/permission/tests.py --ds=devops.test_full_settings --basetemp=.pytest_cache/t14-permission-final -q`，44 passed，15.38 秒。
- 前端事件同步：`node --test scripts/test-run-event-stream.cjs`，4 passed；覆盖超过 20 页终态补拉、尾页失败重试、A→B→A 旧请求隔离、卸载取消。
- 项目类型检查：`vue-tsc --noEmit --skipLibCheck` 通过。额外不带 skipLibCheck 的检查失败于第三方依赖声明，未修改依赖以绕过。
- 本轮运行详情与类型定义 ESLint --fix 后通过。
- 改动页面与请求层使用项目直接 ESLint 可执行文件检查通过；仓库 `npm run lint` 未运行，原因是当前机器 npm 启动器指向不存在的 Roaming npm-cli.js。该环境问题未修改依赖或全局工具。

## 未完成的交付门槛

以下各项的详细执行方式、环境要求、命令和回传要求见 [acceptance-intranet.md](acceptance-intranet.md)，由内网 Agent 在隔离环境执行。

- T14 审计、目标选择、创建、节点、主机、日志、取消和重试的完整浏览器联调；普通角色与 ops 角色的按钮/API/隐藏详情路由一致性。
- ~~隔离 MySQL 空库初始化与并发序列、幂等、锁重试验证~~（2026-09-09 本机完成，见 acceptance-results/mysql/）。
- 真实 Linux Runner 成功、失败、取消以及多主机、SSH key、网关和 WinRM 验证。
- 真实 Redis 单次票据、2 个 API/ASGI 实例和 2 个 Worker、共享归档验证（用户暂缓）。
- Worker 终止、Redis 中断、浏览器断线恢复、重复事件和多消费者故障注入（用户暂缓）。
- 10 个运行、20 个订阅者、合计 100 events/s 持续 10 分钟的合成负载（用户暂缓）；目前没有这些指标，不作容量承诺。
- 根据实际托管方式生成并验证唯一一套部署配置；用户授权后的入口切换与观察。

模拟接口只用于前端交互检查，不能作为真实执行、通知、Redis 或数据库集成证据。每项通过后须补充实际命令、环境、结果和产物位置。
