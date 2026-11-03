# 第二轮整体代码审查

本轮未修改业务代码。范围为账号权限、一次性定时任务生命周期、云导入默认值、执行目标连接方式和配置页状态；同时复跑现有后端测试。未连接真实主机、云账号或消息渠道。

## 新确认问题

1. **P1：个人资料接口允许提权。** apps/user/views/user_profile.py:206 复用 UserProfileSerializer，该 serializer 的 Meta 仅 exclude password（apps/user/serializers.py:12），没有限制 is_superuser、is_staff、role 等字段。给普通用户仅授予 PUT /api/v1/users/profile 权限后，提交 is_superuser=true 成功，用户变为超级管理员。建议个人资料使用独立白名单 serializer，同时限制普通用户管理权限授予超级权限字段。应先修字段权限，再调整个人资料的默认访问权限。

2. **P2：已完成一次性任务可以重新启用一个过去的时间。** apps/jobs/serializers.py:519 仅在 run_at 发生变化时验证未来时间。已投递的单次任务 enabled=true 更新被接受；原 occurrence 已存在 DISPATCHED 结果，后续触发被去重，业务列表却保持启用。建议重新启用时要求未来执行时间，或提供“重新安排”操作。

3. **P2：过期时间等于执行时间仍允许创建。** apps/jobs/serializers.py:535 只拒绝 expires_at < run_at，但运行入口使用 now >= expires_at 判断过期。两个时间相同的任务创建成功，实际没有有效执行窗口。应要求过期时间严格晚于执行时间。

4. **P2：新导入 Windows 主机默认连接方式与系统不匹配。** apps/cmdb/tasks.py:78 对未提供连接参数的主机统一默认 SSH/22。云采集器返回 Windows 操作系统，但不返回连接协议；导入结果因此仍为 SSH。apps/ops/workflow/inventory.py:48 又按连接协议划分 Windows/Linux inventory。建议新建云主机按操作系统提供默认连接策略，或明确要求确认后才能执行；已有人工作业配置必须继续保留。

5. **P2：按配置展示名称搜索可能无结果。** frontend/src/views/manage/config/modules/config-group-view.vue:65 的 matchKeyword 仅使用原始 configName/configKey/remark，而字段展示使用 config-fields.ts 的 label。例如种子名称“登录失败锁定次数”，界面显示“连续登录失败次数”，搜索后者返回 false。需要统一展示与搜索的名称解析，并纳入控件提示说明。

## 复现证据

- docs/review_round2_probes.py：4 项隔离测试分别确认提权、无效单次时间窗口、过期时间重新启用、Windows 默认 SSH。均为应拒绝/应匹配却失败的复现，放在 docs 中避免改变现有正常测试收集。
- 前端直接调用实际 matchKeyword 与 resolveFieldDef：展示“连续登录失败次数”，searchMatches=false。
- 现有完整后端测试：604 passed、6 skipped、25 subtests passed；两条 django-celery-beat 第三方弃用警告。新增复现位于 docs，不在默认 apps 测试收集中，因此原测试通过不代表上述四个漏洞不存在。
- 上一轮的调度延迟投递、到期补跑、云同步保护、密码/上传校验不重复计为本轮新增问题。

## 尚未接入的配置功能

上一轮已记录的默认头像联动、动态登录失败锁定、动态 JWT 有效期、审计日志自动保留和媒体路径动态配置仍待实现。本轮未将其算作新增发现，也未认定保存这些配置即代表功能生效。
