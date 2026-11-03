# 全局审查修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 关闭 2026-10-20 审查发现的权限、数据丢失、执行可靠性问题，统一主要配置/列表弹层，并补齐云同步的确认与状态闭环。

**Architecture:** 保持 Django 现有资源边界和动态路由。字段校验与原子性放后端；前端复用现有 hook、Element Plus 和主题变量。新增同步预览信息保持兼容旧响应，不修改已有运行历史。

**Tech Stack:** Django、Celery、Vue 3、TypeScript、Element Plus、pnpm。

**Spec:** backend/docs/2026-10-20-global-review.md（用户已同意推进）

## Global Constraints

- 保留当前工作区所有既有修改，不重建或清空工作区，不自行提交。
- 前端命令在 frontend/ 中使用 pnpm；禁止 any、硬编码颜色、硬编码页面路由。
- 后端验证仅 devops.test_full_settings，模拟云/通知/执行，不连接真实业务资源。
- 表头及普通表格内容居中；长故障正文按阅读需要左对齐。
- 凭据明文不进入响应、审计快照或历史预览。

## Review Focus

- 停用角色后立即失权，个人资料写接口不能修改权限字段。
- 关联 ID 非法、重复或请求失败时，旧关联必须完整保留。
- 修改主机名称不能改变内存、标签和连接配置。
- 定时版本缺失、过去的一次性时间、异步告警重试必须有确定结果。
- 无变化资产不应冒充更新；新旧 Worker/预览响应仍可处理。

## Task 1：权限与关联原子性

**Files:** backend/apps/permission/services.py；backend/apps/user/serializers.py、views/user_profile.py；backend/apps/cmdb/views.py；对应正式测试。

- [x] 将停用角色、个人资料路由/字段、关联替换失败的探针转为正式失败用例。
- [x] 角色过滤、个人资料白名单、同路径方法映射；关联先验证再在事务中替换。
- [x] 执行权限、用户、CMDB 正式回归测试。

## Task 2：调度与通知

**Files:** backend/apps/jobs/serializers.py、tasks.py、alerts.py、models.py 及必要迁移；backend/apps/automation/views.py；对应测试。

- [x] 测试时间相等、过去时间重新启用、删除被调度引用的流程。
- [x] 添加删除引用保护/空引用防御，补时间边界校验。
- [x] 测试渠道已删除和故障后原运行被重试；冻结故障上下文，禁止改投渠道。
- [x] 验证调度、失败告警和流程版本回归。

## Task 3：前端数据与布局

**Files:** frontend/src/views/cmdb/host、manage/config、automation/resources、task/schedule；公共 table hook/全局主题样式中必要的规则。

- [x] 主机内存无损换算、关系读取失败保护、切分组分页同步；配置展示名参与搜索。
- [x] 统一表格居中、抽屉视口上限、模块参数 grid、主机工作台高度、容量显示。
- [x] 检查受影响组件 ESLint、typecheck；必要数据逻辑使用行为测试。

## Task 4：云同步闭环与诊断

**Files:** backend/apps/cmdb/cloud.py、tasks.py、sync_preview.py、cloud_diagnostics.py、views.py；frontend/src/views/cmdb/source、host/modules/cloud-import-drawer.vue；cmdb API/types。

- [x] 测试 EIP、Windows 默认协议、字段对比、未变化、明确空值和缺失值。
- [x] 实现云字段对比和未变化计数；展示待同步规格和变更详情。
- [x] 分项检查主机/磁盘查询权限，最多 30 区域配置以已测/未测明确返回；凭据不外泄。
- [x] 同步记录按需轮询，结束刷新关联账号/资产；统一筛选栏和操作文案。

## Task 5：配置/环境生效与验收

**Files:** 现有系统配置定义、健康检查和前端状态展示；backend/docs/2026-10-20-global-review.md。

- [x] 未接入运行逻辑的配置明确标为暂不生效并限制编辑，不能虚假承诺重新登录生效。
- [x] 健康检查补云 SDK、加密配置可用性与部署版本标识；不返回密钥。
- [x] 合并后运行后端全量隔离测试、前端行为测试、typecheck、相关 lint 和 build。
- [x] 更新审查关闭状态和手工验收清单，明确真实云/浏览器验收的限制。
