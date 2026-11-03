# 监控集成接口对齐检查

范围：Consul、监控目标、动态纳管、云资源与治理、JumpServer、漏洞订阅；包含相关云账号和通知模板列表依赖。

## 固定契约

- 所有页面请求经过现有 request 封装，成功数据从 `{ code, data, msg }` 的 `data` 读取。
- 显式分页使用 `pageNum`、`pageSize`，返回 `{ list, total, page, size }`。不带分页参数的标准列表返回数组。不要混用自动化资源封装中的 `records/current`。
- 本轮接口保持 serializer 的 snake_case 字段；通知配置内部约定保持 `templateId`、`receivers`。JMS 预览提交 `host_ids`，确认提交 `preview_id`；动态纳管确认提交 `preview_token`。
- 云策略 `balance_threshold`、余额 `amount` 是十进制字符串；编辑表单显式转换为数字，保存传数字。CPU `value` 是数字。
- 云采集成功为 `succeeded`，漏洞采集成功为 `success`，通知送达成功为 `success`；前端分别声明各自状态集合。
- `expires_at`、采样/结束时间等可空字段按接口含义处理，不将空值当作成功或当前时间。
- 连接列表不返回明文或密文凭据；用 `has_secret`、`has_token` 表示已保存。编辑留空保留凭据。JumpServer 保存仅发送可编辑字段，不回传读取到的执行人、已选主机和状态字段。
- 页面管理权限不代表采集执行权限。没有执行权限不能启用云采集；修改已有云策略需要执行权限。动态纳管预览也要求资产读取权限。停用的 JMS 连接不能发起测试或同步。

## 自动核对

共享的 `observability-api-contracts.json` 来自实际前端 API 函数的调用输出，包含67组路由/方法组合。前端契约测试检测请求变更，后端测试解析同一清单，检查路由、HTTP 方法和权限种子；另用测试数据验证18类列表的真实响应包裹、分页、敏感字段及金额类型。

在 frontend 目录运行 `pnpm test:contracts`。在 backend 目录运行 `poetry run pytest apps/monitoring/test_api_contracts.py`。

接口有意调整时，在 frontend 目录运行 `pnpm exec node scripts/observability-api-contracts.cjs --write` 更新清单，然后执行前后端检查。不能只更新快照来忽略后端失败。

本轮相关后端180项测试通过。测试使用隔离数据库及合成数据，没有调用真实云 API、Consul 或 JumpServer，不代替真实环境端到端验收。当前文档不声明历史项目中全部模块均已完成接口审计。
