# Consul 与监控管理：首批部署和验收

## 已交付边界

新增 Django apps：`consul`、`monitoring`。前端动态菜单：监控管理 → Consul 管理 / 监控目标。

- 连接配置、ACL Token 加密保存、留空保留、连接测试；不返回 Token。
- 当前 Agent 实例、节点/服务健康检查聚合、Tags/Meta 查看；外部实例只读。
- 主机/MySQL/Redis Exporter 与 Blackbox 目标配置，可关联 CMDB 主机；关联不代表已经安装 Exporter，也不自动跟随资产 IP 变化。
- 注册预览、Celery 注册/更新/注销、同步历史、失败诊断、重复提交互斥、长期未完成任务恢复。
- 已注册或注册结果不确定的目标先注销再删除/更换连接；目标删除后仍保留独立同步历史。
- Prometheus Consul 服务发现配置与基础告警规则预览，Token 不包含在导出结果中。
- 复用 RBAC、菜单初始化和审计，审计领域新增“监控管理”。

## 部署步骤

先备份部署数据库。以下命令由部署环境执行；本次开发没有连接部署数据库。

在 `backend/` 运行：

```text
poetry run python manage.py migrate
poetry run python manage.py init_system_settings
```

同批部署前端，重启 API、订阅 `task` 队列的 Celery Worker 和 Beat。恢复任务由 Beat 每分钟检查一次，超过十分钟仍未完成的同步标记失败，可在排查后重新提交。不要在 Web 进程启动独立调度器。

普通角色需要分配新菜单及对应新增、编辑、测试、同步、注销、删除按钮权限；目标编辑所需的连接列表和主机查询权限随按钮依赖配置。重新登录获取菜单。初始化沿用现有规则，不重置用户已配置图标。

确保配置有效的 `DEVOPS_CREDENTIAL_ENCRYPTION_KEY`。API 与 Worker 使用同一密钥，备份时独立保管密钥，轮换遵循既有凭据流程。

## Consul 前置条件

Agent 地址必须稳定、可由 API 与 Worker 访问；Agent 对自身注册的服务负责。本批不支持把地址切到另一台 Agent 后继续注销旧实例，不支持反向代理路径前缀和 Enterprise namespace/partition。

配置的数据中心应与当前 Agent 所在数据中心一致；连接测试返回实际 Agent/数据中心供核对。多数据中心分别建连接。跨节点 Catalog 浏览尚未交付。

Token 的具体权限按部署策略配置：连接测试需要读取 Agent 信息，实例展示需要读取 Agent 服务和检查，注册/注销需要管理对应 `devops-*` 服务。Prometheus 使用单独的只读 Token，允许读取所需服务、节点及健康信息，不复用平台写权限 Token。

TLS 校验默认开启，不提供“忽略证书”开关；使用受信任的证书。HTTP 仅用于受控网络，生产建议 HTTPS。请求禁用代理环境继承及 HTTP 重定向，设置连接和读取超时。监控标签、Meta 和探测 URL 不应填写密码、Token 等机密；探测 URL 会进入 Consul 元数据及 Prometheus 配置。

## Prometheus / Exporter

先部署所需 Exporter。默认端口建议：Node 9100、MySQL 9104、Redis 9121、Blackbox 9115；应以实际部署为准。

Blackbox 目标的 address/port 是 Exporter 地址，`probe_target` 是被探测 HTTP(S) URL。模块必须已存在于 Blackbox 配置；当前表单只覆盖 HTTP(S) 探测。Consul TCP 检查只检查 Exporter 端口，不反映站点业务健康。

将生成的 `scrape_configs` 片段合并到现有 Prometheus 配置。配置 ACL 时，通过 `authorization.credentials_file` 引用挂载到 Prometheus 的只读 Token 文件，默认示例路径 `/etc/prometheus/secrets/consul.token`。生成配置不包含真实 Token，也不自动修改 Prometheus。

Consul Meta 映射成 `consul_` 前缀标签，Tags 映射成 `consul_tags`。生成的基础规则覆盖 Exporter 采集失败、Blackbox 采集失败和探测失败，持续五分钟触发。保存规则文件并配置 `rule_files`，运行部署环境的 `promtool check config` / `promtool check rules` 后再重载。Alertmanager 通知路由需要另行配置，本批没有将 Alertmanager 告警自动转发到平台通知渠道。

注册更新使用 `replace-existing-checks=true`，移除平台不再配置的检查；不会为健康异常自动注销实例，避免网络短暂失败造成监控消失。

## 手动验收

1. 新建连接、填写 Token，测试成功；编辑不填 Token 保存，再次测试仍成功。
2. 新建目标，关联主机并确认 Exporter 地址；预览不产生外部写操作。
3. 同步后查看记录成功、Consul 管理中出现平台纳管实例；同 ID 外部实例不会被覆盖。
4. 修改标签/端口后显示待同步；重新同步后观察 Consul 更新。关闭 TCP 检查后重新同步，旧平台检查应移除。
5. 配置 Blackbox HTTP 目标，合并 Prometheus 配置，确认正确请求 Exporter 的 `/probe?target=...&module=...`。
6. 模拟 ACL 拒绝、网络超时，界面有失败原因且不会把读取失败当作空清单。外部写入结果不确定时先重新同步/注销确认。
7. 注销后实例消失，目标可删除，同步历史仍可通过只读同步记录 API 和审计追溯。
8. 普通无权限账号无法访问或修改，拥有只读菜单的角色看不到写操作按钮。

## 后续批次

第二阶段已补齐 Catalog 跨节点只读浏览、选定主机批量接入与目标级定时同步，升级和行为见 [第二阶段部署说明](2026-10-27-monitoring-phase2-deployment.md)。下方为首批完成时的后续规划记录。

Catalog 跨节点浏览、资产批量/定时接入、RDS/Redis 云资产扩展、云监控指标采集、余额/到期治理、JumpServer 及漏洞订阅未在本批实现。

## 官方接口参考

- [Consul Agent 服务注册及检查替换](https://developer.hashicorp.com/consul/api-docs/agent/service)
- [Consul Token 请求头与 Bearer 认证](https://developer.hashicorp.com/consul/api-docs/api-structure)
- [Prometheus Consul SD 配置](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#consul_sd_config)
