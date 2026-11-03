# 漏洞公告订阅

固定来源为 `https://avd.aliyun.com/`，解析契约参考仓库 `TenSunS-main/flask-consul/units/avd/avd_list.py` 的五列官方表格。此模块订阅公告，不对资产执行漏洞扫描。

- API：`/api/v1/security/subscriptions` CRUD；`POST /{id}/collect` 手动采集；`/api/v1/security/advisories`、`/api/v1/security/collections` 只读，支持分页。
- 页面：`frontend/src/views/monitoring/security/index.vue`，菜单组件 `view.monitoring_security`。配置启用、5～10080 分钟间隔、任一关键词、严重程度、已有通知模板和接收人；采集记录收在漏洞公告卡片的右侧抽屉中。新增订阅保存后，具备采集权限的账号会立即触发一次基线采集，无需等待下一个 Beat 周期。
- Beat 每分钟调用 `security.sweep`：到期订阅合并为一次共享抓取任务 `security.collect_source`（task 队列），官方源只抓取一次，落库后各订阅按自身关键词/严重程度匹配通知；手动采集走 `security.collect` 独立抓取。已有 `jobs` 通知恢复任务负责失败通知重试。
- 订阅行锁确保同一订阅只有一个待执行/执行中任务。超过 10 分钟的采集与共享抓取（`SecurityFetch`）标为失败；旧 Worker 在写入前锁定并复核状态，避免复活已回收任务。
- 每次执行先后复核执行账号的在职、启用及 collect API 权限。首次成功采集建立基线，不发通知；后续以公告稳定编号和内容指纹识别新公告/重要变化，每个订阅单独维护观察记录。
- 失败/验证码/重定向/源结构变化不作为空成功；官方来源未提供严重程度时保留为 unknown（未评级），不推测风险等级。仅接受固定官方域名 HTTPS 详情链接；响应限制 2 MB、20 秒读超时。公告只作为数据持久化和文本显示，不执行内容，不渲染不可信 HTML。
- 通知复用 automation 通知模板、渠道加密凭据、NotificationRecord 与 jobs.alerts 失败重试，alert_key 以 SHA256 去重。采集队列数量与通知发送成功明确区分。无新增凭据存储。

验证使用官方结构的离线 HTML fixture、mock 网络和发送器；采集测试没有访问真实 AVD，也没有发送真实通知；开发时仅人工查阅官方页面核对表格结构。需上线前验证当前源站结构、Worker/Beat、有效模板和通知渠道。源站结构不匹配会留下失败记录，不能宣称已完成真实联调。
