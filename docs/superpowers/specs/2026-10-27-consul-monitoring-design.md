# Consul 与监控管理首批设计

用户已确认使用 Consul，并批准新增 apps/consul 和 apps/monitoring。

方案：Django ORM 保存配置，Consul 为实际服务注册及健康状态来源。复用 CMDB 资产、Fernet 凭据加密、DRF/RBAC、审计、Celery。原 Flask、Consul KV 数据库和 APScheduler 不引入。

首批范围：Consul 连接 CRUD、留空保留 Token、连接测试；只读查看指定 Agent 的服务及节点/服务检查聚合状态；本平台纳管实例注册/更新/注销；监控目标 CRUD（主机、MySQL、Redis、Blackbox）、关联 CMDB 主机、Tags/Meta、注册预览、显式同步/注销及记录；Prometheus Consul 配置及基础规则导出；两个统一风格页面及动态菜单。Catalog 跨节点浏览另批交付，不混淆当前 Agent 的写操作归属。

边界：Consul Agent 注册/注销必须发到同一连接，服务查询展示该 Agent 所有实例，外部未纳管实例只读；不承诺全数据中心实例写操作。平台注册 ID 使用持久 UUID 前缀。禁止覆写外部同 ID 实例。平台标识放 Meta，不接受用户覆盖保留键。目标变更后展示待同步，注销前不能删除或移动到其他连接。停用连接禁止写操作。

Blackbox 的服务地址为 Exporter 地址，真实探测目标和 module 放 Meta 并生成 relabel 配置；只配置探测，不由 Django 执行探测。连接 URL 只允许 HTTP(S)，无 URL 凭据、query、fragment；禁止元数据地址和重定向，访问内网 Consul 属于明确授权用途。TLS 默认校验。HTTP 超时，错误脱敏且不返回原始云/Consul响应。

同步先建立 queued 记录并按目标互斥，Celery 执行更新；连接和目标在同步期间禁止编辑/删除。失败保留记录和上次注册状态；不因读取失败注销服务。首批不启用自动清理或定时同步。外部调用后的本地失败可能需要重试，注册操作幂等。

后续：自动同步、余额/到期治理、云监控指标采集、JumpServer、漏洞订阅分别交付，不在本批宣称完成。无真实外部系统和部署数据库操作。
