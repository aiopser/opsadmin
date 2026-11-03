# 2026-10-20 前后端审查

本轮只做审查与隔离复现，没有修改产品代码。覆盖账号权限、资产编辑与云同步、流程和定时任务、失败通知、配置页与主要编辑弹层。没有连接真实云平台、主机或发送通知。UI 结论来自当前模板、样式和已有截图，尚未逐页做浏览器验收。

后续状态：用户确认后已实施修复。原始问题记录保留；关闭结果、部署步骤和验收以 `backend/docs/2026-10-20-review-remediation-acceptance.md` 为准，旧诊断探针已转换为对应模块正式回归用例。

## 优先关闭的缺陷

| 优先级 | 问题、触发与影响 | 位置 | 修复方向 |
| --- | --- | --- | --- |
| P1 | 停用角色后，即使重新生成并加载策略，原 DELETE 等 API 权限仍通过 | `backend/apps/permission/services.py:87` | 生成策略和成员关系均排除停用角色，刷新权限缓存，补撤权用例 |
| P1 | 主机分组/标签、分组成员替换先删后插，非法或重复 ID 导致报错后旧关联永久丢失 | `backend/apps/cmdb/views.py:392`、`:459` | 先验证 ID、去重，事务内整体替换；失败完整回滚 |
| P1 | 主机标签读取失败仍允许编辑保存，默认空标签被当作明确清空 | `frontend/src/views/cmdb/host/modules/host-list.vue:494`、`:506`、`:570` | 区分尚未加载/加载失败/明确空集合；未加载成功禁止覆盖关系 |
| P1 | 编辑主机时内存 MB 转 GB 使用整数四舍五入，512 MB 变为 1024 MB；仅改名称也会改规格 | `frontend/src/views/cmdb/host/modules/host-list.vue:482`、`:600` | 保留原始 MB 或无损换算；列表显示精确容量 |
| P2（字段风险需同步修复） | 个人资料 GET 与 PUT 各声明相同 `profile` 路径，实际 resolve 只匹配 GET，保存入口不通；内部更新 handler 使用除 password 外全字段 serializer，直接调用可修改管理员标记 | `backend/apps/user/views/user_profile.py:199`、`:205`、`:207`，`backend/apps/user/serializers.py:12` | 合并同路径方法映射，个人资料独立白名单；先补字段限制再恢复写路由。不能把内部调用复现等同于当前外部 URL 可达 |
| P2 | 一次性任务允许过期时间等于执行时间；完成后允许用过去的执行时间重新启用，列表启用但不会再次运行 | `backend/apps/jobs/serializers.py:519`、`:535` | 过期时间严格晚于执行时间；重新启用要求未来时间或提供重新安排入口 |
| P2 | 整个流程删除后，定时任务仍启用且版本引用为空，触发时访问 None.status 报错 | `backend/apps/automation/views.py:316`、`backend/apps/jobs/tasks.py:601` | 删除引用保护；调度处理空引用并停用、记录明确原因 |
| P2 | 失败告警冻结的渠道 A 删除后，会回退到模板当前渠道 B，故障信息投向非原定渠道 | `backend/apps/jobs/alerts.py:49`、`:54` | 冻结渠道不存在时明确失败，禁止自动改投 |
| P2 | 失败通知异步等待/重试期间原运行重试成功，发送时读取当前运行，导致原故障原因消失、状态与失败标题冲突 | `backend/apps/jobs/alerts.py:131` | 创建告警时冻结故障上下文；单独定义恢复通知或取消规则 |
| P2 | 阿里云 EIP 未读取，public_ip_address 为空但 eip_address 有值的实例会被采成空外网地址，重同步覆盖已有值 | `backend/apps/cmdb/cloud.py:321`、`backend/apps/cmdb/tasks.py:167` | 合并固定公网 IP 与 EIP；区分未返回和明确解绑 |
| P2 | 新导入 Windows 云主机默认仍是 SSH/22，后续 inventory 也按连接协议分类 | `backend/apps/cmdb/tasks.py:91`、`backend/apps/ops/workflow/inventory.py:48` | 新建时按 OS 给默认协议，或要求配置后才可执行；保留已有人工连接配置 |
| P2 | 主机列表切分组只重置请求页码，分页器仍在旧页 | `frontend/src/views/cmdb/host/modules/host-list.vue:343` | 使用统一分页重置方法，同时更新请求和分页 UI 状态 |
| P2 | 配置页按原始配置名搜索，不包含界面显示名，搜索“连续登录失败次数”无结果 | `frontend/src/views/manage/config/modules/config-group-view.vue:65` | 展示和搜索共享同一字段定义，并纳入说明文本 |

其中个人资料字段白名单、一次性任务两个时间边界、Windows 默认连接方式、配置展示名搜索是上轮遗留，本轮重新核实仍存在。

## 前端布局应统一的部分

1. **表格列规则应共用。** 最近已调整的主机/同步记录表格有局部居中覆盖，通知渠道名称、发送记录的时间/模板/渠道仍走默认左对齐。位置：`frontend/src/views/automation/resources/notification/index.vue:441`、`:703`。统一表头和普通内容居中、数量等宽数字、状态标签尺寸、操作列宽度；长错误正文在详情中按阅读需要左对齐。
2. **抽屉尺寸需要适配实际窗口。** 主机、云账号、定时任务固定 720px，执行资源新建固定 860px；版本编辑已有 `min(860px, 100%)`，实现不一致。窄窗口会裁切。位置：`host-list.vue:816`、`account-operate-drawer.vue:218`、`task/schedule/index.vue:590`、`automation/resources/modules/command-page.vue:1208`。统一尺寸档位和视口上限，长表单内部滚动、底部操作稳定可见。
3. **模块参数表头与输入列应共用布局定义。** `frontend/src/views/automation/resources/modules/version-form-fields.vue:257`、`:265`、`:287`：表头与带内边距的参数行错位，六列固定宽度在窄窗口溢出。改共用 grid 列定义，小窗口转参数卡片。
4. **主机列表高度不应固定 520px。** `frontend/src/views/cmdb/host/modules/host-list.vue:768`：低高度屏幕分页容易落到页面外，高屏则留大片空白。桌面使用剩余高度、表格内部滚动；小屏保留自然页面滚动。
5. **筛选栏与页面操作区还存在两套布局。** 云账号卡片头部是无标签搜索输入 + 刷新 + 新增，通知/定时/系统配置采用带标签筛选栏。建议统一为上方筛选、下方内容操作；复杂卡片不重复大段帮助和页面标题。云账号位置：`frontend/src/views/cmdb/source/modules/cloud-account-list.vue:113`。
6. **信息应该先准确再做字体微调。** 主机内存显示四舍五入会失真；“40G / 100G”未解释系统盘/数据盘；原始区域 ID 应保留，配中文区域解释。位置：`host-list.vue:223`、`:231`、`:237`。正文默认颜色和常规字重，强调色用于当前选项、主要动作和状态。

建议把规则落实到已有表格 hook/公共组件及统一弹层样式，配一份代表页面验收清单，避免继续单页修补。

## 建议补齐的功能

| 功能 | 当前缺口 | 建议 |
| --- | --- | --- |
| 同步字段变更对比 | 预览只用实例存在与否区分新增/更新，不计算真实差异；CPU、内存、磁盘变化在确认前看不到 | 展示未变化/新增/更新/无效，支持查看字段旧值 → 新值，并说明人工字段保留规则。依据 `backend/apps/cmdb/sync_preview.py:54` |
| 同步状态闭环 | 提交后打开记录只请求一次，排队和运行状态不会自动更新 | 抽屉打开时按需轮询未完成记录，完成后刷新账号最近同步时间和资产列表；终态失败提供可复制原因。依据 `sync-record-drawer.vue:104` |
| 分项连接检测 | 当前“测试连接”只测 DescribeInstances，实际完整同步还需要 DescribeDisks；账号可配置 30 个区域而测试一次最多 5 个 | 分别显示认证、主机查询、磁盘查询结果；明确已测/未测区域，不把部分通过称为全部可同步 |
| 环境自检扩展 | 已有 Redis/Worker 等健康页，但缺少云 SDK、加密密钥可用性及 API/Worker 部署版本一致性 | 在已有健康检查中补依赖与服务版本，不暴露密钥；上线时发现“前端新、后端旧”“SDK 未安装” |
| 配置生效状态 | JWT 有效期、连续登录失败锁定、日志保留、媒体路径目前能保存，但未找到对应运行时消费；令牌有效期提示“重新登录生效”与实现不符 | 接入运行时策略，或明确标记暂不生效并禁用编辑。依据 `frontend/src/views/manage/config/modules/config-fields.ts:93`、`backend/devops/settings.py:221` |

## 验证与范围限制

- `docs/review_round2_probes.py`：4 个预期正确行为断言失败，重新确认上述遗留问题；个人资料项为 handler 直接调用，已另外核对真实路由仅匹配 GET。
- `docs/2026-10-20-review-probes.py`：4 个预期正确行为断言失败，覆盖停用角色、关联修改失败回滚、分组重复成员、阿里云 EIP。
- 通知/删除流程隔离探针：3 项通过，断言并确认异常行为，使用请求/入队 mock，无真实通知。
- 前端直接执行当前 `matchKeyword` 与 `resolveFieldDef`：显示“连续登录失败次数”，搜索匹配结果为 false。
- 未宣称完整产品或真实浏览器验收通过。上面列出的失败探针需在修复时转为正式回归用例；此前正常测试通过不代表这些拒绝场景已覆盖。

推进顺序：先关闭权限与数据丢失问题，再修运行/通知/定时状态闭环，再统一表格、筛选栏、编辑弹层，最后补同步差异与环境自检。每批都需要异常路径验收。
