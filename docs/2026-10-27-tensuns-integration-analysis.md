# TenSunS 功能接入分析

分析对象：仓库内 `TenSunS-main/` 源码，不代表上游最新版本。

## 已核对的实现

- `flask-consul/manager.py`：Flask 注册业务蓝图，启动时依赖 Consul，恢复 KV 中的 APScheduler 任务。
- `units/consul_kv.py`：配置、采集结果、任务等主要通过 Consul KV 保存；不是 Django 关系数据库模型。
- `views/consul.py`、`units/consul_svc.py`：服务实例查询、注册、注销、标签、元数据和健康检查管理；更新采用先删后加。
- `views/blackbox.py`：站点/接口目标维护、分组、批量导入和配置生成；实际探测依赖 Blackbox Exporter、Prometheus。
- `units/cloud/`：阿里云、腾讯云、华为云、AWS 的云资源对接；ECS、RDS、Redis 的实际支持需按提供方分别验收，不假设所有能力一致。
- `units/cloud/azurecloud.py`：存在 Azure 代码，但 manager 未导入，requirements 未列对应 SDK，余额/到期入口是 pass；不能算已完整接入。
- `views/prom/cloud_metrics.py`：云 MySQL/Redis 指标出口分支包含阿里云、腾讯云、华为云，不包含 AWS。
- `views/exp.py`：账户余额、资源到期查询与通知设置。
- `views/jms.py`、`units/jms/`：JumpServer 对接与同步。
- `views/avd.py`、`units/avd/avd_list.py`：阿里云漏洞库 HTML 采集和群机器人通知；HTML 结构变化可能导致解析失效，不能视为漏洞扫描器。

## 与本项目的边界

本项目 `apps/cmdb/models.py` 已有 AssetSource、CredentialRef、AssetHost、分组/标签和同步记录，云提供方为阿里云、腾讯云、VMware、OpenStack、PVE。现有 automation 已有通知渠道、模板、发送记录；现有权限、审计及 Celery 应复用。

建议新增 `backend/apps/monitoring/`，中文入口为“监控管理”。它负责监控接入与服务发现，不再维护第二套云账号、主机资产、用户和通知系统。

| 功能 | 建议归属 |
| --- | --- |
| 云账号、主机、华为云/AWS 资产同步扩展 | 现有 cmdb |
| RDS/Redis 资产目录及来源关联 | 扩展 cmdb，保留独立资源类型 |
| Consul 连接、服务实例与健康状态 | monitoring |
| 站点目标、探测模块、监控分组 | monitoring |
| 资产到监控目标的映射、标签、同步策略与记录 | monitoring |
| Prometheus 发现端点、配置及告警规则生成 | monitoring |
| 云数据库/缓存指标采集与指标缓存 | monitoring |
| 余额/到期采集策略、去重告警 | monitoring，引用 cmdb 云账号和现有通知 |
| JumpServer 对接配置与同步记录 | monitoring 的集成服务，引用 cmdb 主机 |
| 漏洞订阅及通知去重 | monitoring 的独立订阅模块，不宣称扫描资产漏洞 |

## 技术落地建议（待确认）

- Django ORM 为本地配置的权威数据源；Consul 是外部服务发现系统，不承担本站数据库角色。
- DRF API 复用项目响应、鉴权、分页、权限与审计；不保留源项目的独立登录/LDAP 管理入口。
- 后台采集、同步使用 Celery/Beat，显式记录任务状态、重试、互斥和失败原因，不在 Web 进程启动 APScheduler。
- 可选支持 Prometheus HTTP SD，让未部署 Consul 的环境也能使用基础目标管理；这是新增设计，非源项目现成功能。
- Consul/JMS 同步按外部实例标识幂等写入，仅管理本站拥有的记录；采集失败不当作空清单，不删除未知服务。
- 外部 HTTP 调用设置超时、TLS 校验及目标地址策略；明确允许访问的内网 Consul/Exporter，阻止任意请求云元数据地址。凭据加密保存，日志脱敏。
- 云指标异步采集并缓存，抓取端点不逐次阻塞调用云 API；凭据不进入 Prometheus 标签或返回结果。
- 不原样移植旧依赖锁定版本、旧前端或部署脚本。前端使用现有 Soybean Admin、Element Plus 组件与动态菜单。
- 不让“新增监控目标”伪装成“已成功监控”：页面分别展示目标配置、发现同步状态和外部监控可用性。

## 推荐交付顺序

1. 目标管理、站点探测配置、Consul 连接及服务管理、HTTP SD、配置预览、同步记录；同时完成权限与前端闭环。
2. CMDB 资产监控接入、标签映射、自动同步、配置/规则导出；扩展 RDS/Redis 资产及云提供方支持。
3. 余额/到期提醒、云数据库指标、JumpServer 同步。
4. 漏洞订阅、看板链接与运维文档；逐项完成外部系统联调。

以上是源码分析和建议，不是已实现功能清单。新 app 的范围和依赖边界确认后，再编写实施设计与测试计划。
