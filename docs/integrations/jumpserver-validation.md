# JumpServer 集成验证与运维

页面组件：`view.monitoring_integrations`，文件 `frontend/src/views/monitoring/integrations/index.vue`。

API（无尾斜杠）：

- `/api/v1/integrations/jumpserver/connections` GET/POST
- `/{id}` GET/PATCH/DELETE
- `/{id}/test` POST：校验指定节点可访问
- `/{id}/preview` POST `{host_ids:[1,2]}`：仅生成本地十分钟资产快照
- `/{id}/confirm` POST `{preview_id:1}`：仅原创建者确认并入队
- `/{id}/records` GET：最近100条记录

上述路径由全局 DRF 认证与 ApiRBACPermission 校验。任务在执行前、每台资产写入前再次检查确认账号 is_active 和 confirm POST 的 Casbin 权限。授权菜单需要同时包含必要主机查询权限，使既有 CMDB 选择器可用。拥有映射或执行记录的连接禁止删除，停用即可保留审计链。

凭据使用 CREDENTIAL_ENCRYPTION_KEY 加密；列表仅输出 has_secret。编辑 Secret 留空保留原密文。API Key 为 Key ID + Secret，使用 HMAC-SHA256 HTTP Signature，签名 `(request-target) accept date`。不包含登录账号密码或主机账号下发。

兼容目标为 JumpServer v3/v4 的 `/api/v1/assets/hosts/`，非 v2。节点必须输入真实 UUID，平台 ID 由管理员按实例实际配置指定（默认 Linux 1、Windows 5，不自动推断远端平台）。上游请求使用官方 pk 关联对象形状。参考 [官方 API 文档](https://docs.jumpserver.org/zh/master/dev/rest_api/) 和 [官方资产调用示例](https://www.jumpserver.com/blog/jumpserver-api-interface-calls-guide)。集成仅支持明确配置为 SSH 的 active CMDB 主机；WinRM 不自动解释成 RDP。云主机与手工主机共享同一个 AssetHost 来源与选择器。

首次写入前在本地预留 UUID，并把同一 UUID 发给 JumpServer。创建响应必须保留该 UUID，否则记录失败并要求管理员检查版本兼容性；不会悄悄生成第二个映射。重试先查询该 UUID，只有 comment 所有权标记一致才 PATCH；404 可重建同一 UUID。不按名称或 IP 查找接管外部对象，不删除远端未知资产，也不删除取消选择的资产。

Celery Beat 可每分钟调度：

- `apps.integrations.tasks.schedule_jumpserver`：仅周期大于0且已手工确认过主机范围与账号的连接
- `apps.integrations.tasks.recover_stale_jumpserver`：queued/running 超过20分钟标记失败

worker 任务软限制900秒、硬限制960秒，恢复阈值晚于硬限制。每连接确认时锁行互斥；同一记录重复投递不重复执行。失败或陈旧恢复后，用户重新选择主机、预览、确认重试。同步周期为0时仅手工执行。

外部 HTTP 连接3秒、读取15秒超时，不信任环境代理，不跟重定向。禁止云元数据、链路本地、未指定与组播地址；DNS 全结果预检后固定连接到已校验 IP，保留 HTTPS 原主机 SNI、证书校验和 Host。verify_tls 默认 true，仅管理员可显式关闭。错误不会包含上游响应正文或凭据。

验证：`poetry run pytest apps/integrations/test_integrations.py --nomigrations --ds=devops.test_full_settings --basetemp=<独立目录> -q`，10项通过。所有外部调用 mock，覆盖签名、密文保留、预览、主机变化、连接互斥、执行账号停用、创建/更新所有权、保留UUID重试、元数据和重定向拒绝。前端修改文件 eslint 通过。

尚需真实测试环境联调：确认目标 JumpServer 小版本接受指定资产 UUID、pk 关联字段与 API Key 权限、节点/平台实际ID、组织范围、证书信任链以及 Celery/Beat 的部署配置。本实现未访问真实 JumpServer 或部署数据库。
