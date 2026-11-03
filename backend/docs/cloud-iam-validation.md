# 云账号权限矩阵与验收

更新：2026-10-23。以下是当前创建模板及云目录的权限审阅清单，不是已经通过真实账号验收的可直接投产策略。项目由管理员发布模板时明确锁定 Terraform CLI 与 Provider 版本；仓库没有一个适用于所有已发布模板的统一 Provider 版本。部署方必须记录实际 bundle、lockfile 和校验和，再用该版本核对真实 API 调用。

## 当前模板范围

`apps/provisioning/templates.py` 仅创建按量实例，复用已存在的镜像、VPC、子网与安全组；阿里云使用 alicloud_instance 与 alicloud_vswitches，腾讯云使用 tencentcloud_instance 与 tencentcloud_vpc_subnets。公网分配关闭，带 devops_request_id 标签及 prevent_destroy。新建 VPC/安全组、密钥对、快照、EIP、扩容和销毁不在此模板的授权范围。

云账号读取密钥与资源交付写密钥分开保管。目录/普通同步/交付回读不得切换成写密钥来绕过只读权限不足。应用的模板/地域限制与云侧 IAM 是两层约束；都要验收。

## 动作审阅矩阵

下表的 Provider 动作属于需要在锁定版本审计中确认的候选集合；只读目录/同步 API 则可与代码中的 SDK 调用逐项核对。不要用 `ecs:*`、`cvm:*` 或管理员策略代替排查。

| 阶段 | 阿里云 RAM 动作 | 腾讯云 CAM 动作 |
| --- | --- | --- |
| 资源目录 | ecs:DescribeZones、DescribeImages、DescribeInstanceTypes、DescribeAvailableResource、DescribeSecurityGroups、DescribeAccountAttributes；vpc:DescribeVpcs、DescribeVSwitches | cvm:DescribeZones、DescribeImages、DescribeInstanceTypeConfigs、DescribeZoneInstanceConfigInfos、DescribeAccountQuota；vpc:DescribeVpcs、DescribeSubnets、DescribeSecurityGroups |
| 同步、交付回读 | ecs:DescribeInstances、DescribeDisks | cvm:DescribeInstances（当前代码从实例响应读取磁盘，不调用 CBS API） |
| Provider 子网预检查 | vpc:DescribeVSwitches，以及锁定 Provider 数据源实际使用的只读查询 | vpc:DescribeSubnets，以及锁定 Provider 数据源实际使用的只读查询 |
| Provider 创建和等待 | ecs:RunInstances 或 ecs:CreateInstance/StartInstance（取决于锁定 Provider 创建路径），DescribeInstances、DescribeInstanceAttribute、DescribeInstanceStatus、DescribeDisks（仅实际调用项） | cvm:RunInstances、DescribeInstances、DescribeInstancesStatus（仅实际调用项） |
| 标签 | 若 Provider 单独调用，核验 ecs:TagResources、ListTagResources；不能假定 RunInstances 自动覆盖所有后续标签调用 | 若 Provider 单独调用，核验 tag:TagResources、DescribeResourcesByTags；核对锁定版本是否把标签随创建请求提交 |
| 本轮不授予的写动作 | DeleteInstance(s)、StopInstance(s)、ModifyInstance*、CreateVpc、CreateVSwitch、CreateSecurityGroup、AllocateEipAddress 等 | TerminateInstances、StopInstances、ResetInstances*、CreateVpc、CreateSubnet、CreateSecurityGroup、AllocateAddresses 等 |

API 名称和授权动作并非总是一一对应，必须核对官方授权表。阿里云 RunInstances 涉及实例、磁盘、镜像、安全组、交换机等资源类型与条件键；腾讯云也列出了创建涉及的 instance、image、subnet、security group 等资源。为创建尚未存在的实例通常需要限定账号范围内的实例通配资源；不能把所有资源类型都改成某个现有实例 ID。[阿里云 ECS 授权表](https://www.alibabacloud.com/help/en/ram/api-elastic-compute-service)、[腾讯云 CVM 授权表](https://intl.cloud.tencent.com/document/product/598/57095?lang=en)。

按官方动作支持的资源类型填写账号、地域、镜像、网络与安全组限制；某些查询动作不支持资源级限制，需单独语句并通过平台允许列表约束。标签条件必须区分创建时的 request tag 与已有资源 tag，不能只依赖新实例尚不存在的标签。不要照抄另一家云的 ARN/QCS 或条件键。

## 从候选清单收敛到最小策略

1. 使用独立测试账号和低额度项目，记录模板版本、CLI/Provider 版本、lockfile SHA256、账号、地域与计划资源类型。预先安排测试资源清理审批和负责人员。
2. 先给读取账号逐项明确的目录/同步动作，验证目录、单实例回读、分页、磁盘容量、禁用区域和禁止读取的账号均符合预期。
3. 写账号从已审核创建路径所需明确动作开始；在测试环境生成计划并执行一次，收集脱敏云审计中的服务、动作、资源、请求 ID、结果及时间。Provider 缺权时按真实失败调用补充具体动作，不一次加入通配权限。
4. 去除未使用动作，重新执行最小创建用例。独立验证越权地域、镜像、VPC、子网、安全组、数量/配额，以及删除/停止/改配请求被拒绝。验证结束前保持审批和云侧费用监控。
5. 版本升级或模板新增属性后重新验收。Provider 版本、功能和 API 变化都可能改变动作集合；旧的通过记录不能自动覆盖新 bundle。

建议保存以下记录，证据只含测试资源和脱敏请求，不包含 AccessKey、签名、密码或 state 正文：

| 字段 | 内容 |
| --- | --- |
| bundle / template / lockfile | 版本及 SHA256 |
| 云账号 / 地域 / 网络 | 授权边界与测试范围 |
| 阶段 / API action / resource | 云审计观测值及所需策略语句 |
| 允许用例 | 计划、创建、等待、回读、纳管结果 |
| 拒绝用例 | 越权地域、网络、资源与写动作的拒绝码/请求 ID |
| 撤权与重复请求 | 写权限撤销、重复确认、Worker 失联后的恢复结果 |
| 清理及费用 | 经独立批准清理测试资源，确认无遗留费用 |

本轮没有执行付费云创建或真实 IAM 策略变更，因此此清单没有标记“最小权限已验收”。相关责任人与验收记录应纳入部署变更工单，最终状态写入 [当前验证状态](current-status.md)。
