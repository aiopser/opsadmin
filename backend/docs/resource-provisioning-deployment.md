# 资源申请与交付：部署与验收

本次新增的是独立的 Terraform 交付链路。前后端代码已接入；真实云创建尚未验收，不能据此宣称已在生产可用。

代码验证（2026-10-22）：五项审查修复后的完整后端回归 842 passed、6 skipped、25 subtests passed，定向修复回归 29 passed。前端选择依赖测试、范围 ESLint、typecheck、生产构建通过。Django check 无问题，makemigrations 检查无遗漏，Poetry 锁文件检查通过（存在既有元数据弃用提示）。真实 CLI/Provider、云账号和浏览器验收不包含在这些数字中。

## 页面入口

- 任务系统 → 资源申请：申请、生成计划、确认、审批、执行、核实纳管。
- 任务系统 → 交付运行状况：专用 Worker、队列、租约异常、执行环境和状态存储。
- 资源配置 → 资源模板：模板与不可变发布版本；“创建凭据”标签管理单独的写凭据。
- 通知模板 → 变量说明与预览 → 资源申请与交付：查看 delivery 场景变量。

主机资产仍用于查看与维护现有资产。本轮未在主机资产工具栏增加跨页面快捷入口，避免覆盖用户正在调整的主机表格。

## 部署前置条件

1. 备份数据库与已有独立凭据加密密钥。在部署流程执行 `poetry run python manage.py migrate`。
2. 使用现有 `init_system_settings --sync-menu-layout` 同步新菜单与权限。已有的菜单图标保留规则不变。
3. 部署 Linux 专用 Worker：`poetry run celery -A devops worker -Q provisioning -c 1`。不要把普通 Ansible Worker 当作 Terraform 执行环境。
4. API 和专用 Worker 使用同一套部署配置及私有制品存储；Beat 需重启以注册 5 分钟一次的中断恢复任务。每个申请隔离工作目录；数据库锁与唯一执行记录阻止重复 apply。
5. 固定 Terraform CLI 版本、Provider 版本和校验和，安装管理员审核的 Provider 镜像。CLI 配置只允许指定镜像，不配置回退公共下载。运行账号不得有服务器管理权限。
6. 私有目录不可在 media/static 或 Web 服务器公开目录下；应用账号独占。制品加密，临时工作文件只在私有 working 子目录产生，部署时为该目录配置加密磁盘、权限、备份和容量监控。

环境变量（默认不启用真实创建）：

```text
DEVOPS_PROVISIONING_ENABLED=0
DEVOPS_PROVISIONING_ARTIFACT_ROOT=/var/lib/devops/provisioning
DEVOPS_PROVISIONING_TEMPLATE_ROOT=/opt/devops/provisioning-templates
DEVOPS_TERRAFORM_BINARY=/opt/terraform/bin/terraform
DEVOPS_TERRAFORM_VERSION=<安装并验收的精确版本号>
DEVOPS_TERRAFORM_CLI_CONFIG=/etc/devops/terraform.rc
DEVOPS_PROVISIONING_BACKUP_ROOT=/mnt/independent-backup/devops-provisioning
DEVOPS_PROVISIONING_STATE_KEYS={"v1":"<独立生成并妥善保管的Fernet密钥>"}
DEVOPS_PROVISIONING_STATE_ACTIVE_KEY_ID=v1
DEVOPS_PROVISIONING_MONITOR_TEMPLATE_ID=<可选的资源交付通知模板ID；未配置留0>
```

配置完整并通过测试账号验收后，再设置 `DEVOPS_PROVISIONING_ENABLED=1`，重启 API、专用 Worker。资产读取凭据仍保留在云账号中；写凭据在资源模板页面单独维护，不回显已有密钥，留空不覆盖。

## 安装模板包

`provisioning_bundle` 命令生成审核起点，不下载或安装依赖、不执行 plan/apply。分别为 aliyun、tencent 执行，显式提供部署实际使用的版本：

```text
poetry run python manage.py provisioning_bundle --provider aliyun --directory /opt/devops/provisioning-templates --provider-version <精确Provider版本> --terraform-version <精确CLI版本>
```

管理员审核生成的 `aliyun/main.tf.json`，确认按量计费、无公网分配、仅引用已有网络、网络归属预检查和 prevent_destroy。通过部署工具在该目录运行固定版本 Terraform 的 init/validate，生成 `.terraform.lock.hcl`；锁文件应包含实际专用 Worker 平台的 Provider 校验和。

计算摘要：

```text
poetry run python manage.py provisioning_bundle --provider aliyun --directory /opt/devops/provisioning-templates --digest
```

把摘要、账号、地域、可用区、VPC、子网、安全组、允许镜像和规格填写到模板版本中，再发布。包内容变化须新建版本，不能替换包后复用旧摘要。首期每个平台部署一个审核包，业务版本通过允许范围复用它；任意 HCL 上传、模块编辑与多包仓库不在本轮范围。

## 权限分配

菜单默认只关联必要的读取权限，不能凭菜单访问权直接开机。给申请者显式分配 request.create/plan/confirm/execute/reconcile 和指定 credential.use。按账号限制时，为目标账号凭据的具体 `/api/v1/provisioning/credentials/<id>/use` 配置权限，不能授予通配所有账号的使用权。

审批者另需 review、request.list/detail/approve/reject。本人不能审批自己的申请，包括超级管理员。默认所有申请都需他人审批；首期没有开放前端审批策略管理，不能从请求参数关闭审批。

模板、版本、写凭据的维护与发布权限分配给资源管理员。交付详情中的 allowed_actions 只辅助界面，服务端仍独立校验。

## 故障处理

- plan/init 失败：显示阶段、退出码与环境检查指引。原始 Terraform 错误可能含密钥，不直接返回浏览器；本轮未提供脱敏流式控制台。
- apply 超时或中断：结果待核实，禁止自动重试创建。优先检查回读、加密 state 和云平台带有 devops_request_id 标签的实例。
- 45 分钟仍排队或运行：恢复任务标记失败或待核实，不重新 apply。能找到私有工作目录时归档恢复状态；丢失 state 时需要管理员人工确认，不能仅凭名称猜测实例归属。
- 已创建但回读失败：执行成功保持不变，纳管显示失败；点击“重新核实与纳管”，仅查询已有实例 ID。自动回读按 10/30/60/120/300 秒有界重试。
- 写凭据或模板停用：不阻止已有实例使用独立读取凭据纳管；云账号本身停用或回读授权撤销会阻止回读。
- 部分创建：纳管已知资源，其余保留待核实，不销毁已创建资源。
- 通知：可选冻结通知模板，通过现有 NotificationRecord 重试机制投递；通知不能改变云资源执行结果。

临时工作目录、历史 plan/state 的保留清理需部署方按备份和审计要求制定；首期不自动删除仍可能用于恢复的制品。终态申请也可能需要 state 接管，不能随意按文件 mtime 清空目录。远端 Terraform backend、预算审批、自动销毁与生命周期接管属于后续能力。

## 手工验收

先在专用测试账号完成以下用例，再开启生产创建：

1. 新建读取账号与独立创建凭据，模板只授权测试网络与一款规格/镜像。
2. 申请 1 台，生成计划，核对资源地址、账号、地域、数量与参数；确认后仍不能执行。
3. 切换另一审批用户通过，原申请人执行；确认主机实例 ID、资产 ID、CPU/内存与网络正确。
4. 重复点击和重复投递，不得创建第二台；拒绝审批后不得执行。
5. 过期计划、轮换写凭据、修改账号配置、关闭账号后，旧计划执行被拒绝。
6. 提交授权范围外的账号、网络、安全组、镜像和规格，后端拒绝。
7. 中断 Worker，核实不会自动重新开机；保留已有实例和恢复记录。
8. 创建后暂时阻断读取接口，再恢复网络；仅纳管状态变化，执行成功不被改写，不重复创建。
9. 停用模板或写凭据后重试已有实例纳管，读取凭据有效时仍可成功。
10. 通知模板选择资源交付场景，正文包含 `{{ delivery.name }}`、`{{ delivery.phase }}`、`{{ delivery.message }}`；检查发送记录及实际接收。
11. 浏览器核对桌面和窄屏抽屉、空列表、长名称、加载态、错误提示及审批按钮；此步骤尚未以真实浏览器完成。

本轮未调用真实付费云创建，也未执行部署数据库迁移。SDK 的定向实例查询、Provider 网络预检查和实际规格可用性仍需在所锁版本及测试账号上验收。

## 2026-10-22：状态保护与云资源目录

更新锁定依赖（包括 VPC SDK）后重启 API、专用 Worker 和 Beat。本轮新增迁移为 `provisioning/0004_state_protection`，需在维护窗口停止资源写入、备份数据库和旧制品后执行部署迁移；不要在旧 Worker 尚运行时混用两套状态协议。Beat 每 30 秒检查心跳、积压和租约，旧任务的 45 分钟恢复兼容仍保留。

### 状态保护与恢复

主存储与备份必须使用彼此不嵌套的私有路径，部署时落实不同磁盘、存储服务或故障域；代码只能检查路径独立和可读写，不能证明底层设备独立。二者禁止放在 media/static 或任何 Web 服务器公开目录。API 和专用 Worker 均需访问同一套私有存储和密钥环。

state 密钥环独立于读取云账号凭据的加密密钥。轮换时先将新 key ID 加入 `DEVOPS_PROVISIONING_STATE_KEYS`，再切换 active ID；保留历史 key，验证历史备份可读后才考虑下线旧 key，不能直接覆盖同一 ID 的密钥。密钥必须另行离线备份，不能与密文放在同一个可丢失目录。不要把真实密钥写进仓库。

旧制品核对和清理默认只预览：

```text
poetry run python manage.py provisioning_state_index
poetry run python manage.py provisioning_state_index --execute
poetry run python manage.py provisioning_state_index --repair
poetry run python manage.py provisioning_state_index --repair --execute
poetry run python manage.py provisioning_artifact_gc
poetry run python manage.py provisioning_artifact_gc --execute
```

索引命令只登记可校验的旧 state；修复模式从仍可验证的主副本或备份重新建立保护，不会 apply。清理仅处理已登记且过期的计划/诊断制品，活动或结果未知的任务保留；state 统一保留，未来只有可信销毁记录后才启用退役保留期限。未登记文件只报告数量和大小，不自动删除。不要按文件 mtime 递归清空目录。

恢复权限为 `request.state-versions`、`request.restore-preview`、`request.restore-confirm`，相互独立；普通详情权限不包含恢复。详情里先校验备份，再确认具体版本和实例 ID。恢复新建业务状态版本，不伪造 Terraform serial、不回滚云资源，仅触发只读回查。旧 serial、lineage 冲突、运行中或结果待核实的写任务禁止恢复；没有 force 入口。

监控每轮按上次更新时间轮换校验最多 100 个活动 state 的主副本与备份，检查文件、解密、归属及摘要。发现异常后标为保护异常；文件修复且再次校验通过后解除异常。主副本损坏时仍可从有效备份发起恢复预览；保护异常不等于备份一定可恢复，预览和确认都会独立验证备份。页面校验时间表示最近一次成功校验时间。

验收必须覆盖：主副本丢失但备份有效；备份不可写但创建成功保持成功；旧密钥缺失；过期/重复恢复预览；空闲 Worker 心跳、租约失效及旧进程迟到；故障通知及恢复通知去重。应用关闭创建开关时不因“无创建 Worker”产生故障告警。

### 只读云资源目录与权限

申请目录 `GET /api/v1/provisioning/catalog` 需要目录读取、模板版本详情与具体创建凭据 use 权限，先授权再命中缓存。管理员目录使用独立的 `/catalog/configuration` 路由，还需要版本维护及目标云账号详情权限；不能用 query 参数切换管理权限。

| 平台 | 只读目录操作 |
| --- | --- |
| 阿里云 ECS | DescribeZones、DescribeImages、DescribeInstanceTypes、DescribeAvailableResource、DescribeSecurityGroups、DescribeAccountAttributes |
| 阿里云 VPC | DescribeVpcs、DescribeVSwitches |
| 腾讯云 CVM | DescribeZones、DescribeImages、DescribeInstanceTypeConfigs、DescribeZoneInstanceConfigInfos、DescribeAccountQuota |
| 腾讯云 VPC | DescribeVpcs、DescribeSubnets、DescribeSecurityGroups |

上述操作加在云账号的读取凭据上，不能复用创建密钥扩大目录权限。写凭据仍只给已审核 Provider 实际创建及轮询所需动作，按账号/地域/网络限制；以测试账号的审计记录核对锁定 Provider 的真实调用，不授予通配管理员权限。

新模板可选择“按规则发现”，以 schemaVersion=2 发布账号、地域、镜像前缀、CPU/内存和网络/安全组标签约束；空标签表示不按标签限制。固定清单及历史已发布版本保持原规则，不自动升级。管理员“浏览资源”用于配置账号目录，不代表申请人可访问全部结果。

普通目录缓存 120 秒，可用性 30 秒；“重读”明确跳过缓存。分页游标绑定用户、账号配置、模板规则及筛选条件，10 分钟过期。精确库存和配额余量未明确返回时为未知，不显示 0 或充足。生成计划冻结资源展示快照，执行前重新读取归属、兼容性与可用性；读取成功不等于库存已预留。

部署后用只读测试账号核对 SDK 返回字段、分页、标签、权限拒绝、限流及长名称；浏览器核对账号/地域/可用区切换、窄屏、未知容量、售罄、恢复确认及空/错误态。真实 CLI/Provider、实云和浏览器验收尚未完成，不能以自动测试代替。
