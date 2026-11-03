# 开发与贡献约定

本仓库的强制规则见 [AGENTS.md](AGENTS.md) 与 `.trae/rules/`。本文件补充日常变更、验证和交付方式；后端检查清单及 CI 配置以 [开发质量门槛](backend/docs/development-quality.md) 为准。

## 开始变更

先核对 `git status` 与目标文件的既有改动。不要重置他人工作，不要为一个业务修复全量格式化历史文件。问题修复应先有能够触发问题的回归，再改实际函数或接口。

前后端分处 `frontend/` 与 `backend/`。前端只使用 pnpm，所有前端命令在 `frontend/` 运行；后端依赖由 Poetry 锁定。测试使用独立数据库、缓存、队列、目录和密钥，禁止把工作区默认部署配置作为测试服务来源。

## 前端

- 编辑 `.vue` 前读取 `.agents/skills/vue-sfc-structure/SKILL.md` 和 `ui-details/SKILL.md`；编辑 TS/JS 及 SFC 脚本前读取 `typescript-functional-style/SKILL.md`。
- 使用 Vue 3 `script setup`、TypeScript、Element Plus、UnoCSS，模板保留单一根元素。复用 `@sa/*` 与 `src/hooks/`，不引入其他 UI 库、`any` 或硬编码颜色。
- 后端菜单决定业务路由；使用注册的路由名和参数，不在组件中拼接路径。
- API DTO 在服务边界显式转换。顶层字段采用该接口已声明的协议，嵌套用户参数名不自动改写；例如后端用户 `must_change_password` 映射为前端 `mustChangePassword`。
- 异步资源请求同时校验请求代次和资源身份。脚本应绑定脚本 ID/类型；Git 正文应绑定仓库/ref/path；切换、清空、关闭与卸载使旧响应失效。
- 保存成功只能确认实际提交时的快照。保存中禁用编辑与重复提交；仍出现新变更时保留 dirty 状态，禁止发布旧内容。
- 执行确认保留预览返回的 `executionRequestId`；网络失败后重复确认使用原 ID。重新手动预览才使用新 ID，不把确认摘要当作幂等锁。

在 `frontend/` 执行：

```powershell
pnpm typecheck
pnpm lint
pnpm test:contracts
pnpm build
```

`test:contracts` 自动运行所有 `scripts/test-*.cjs`，也可按变更范围用 `pnpm exec node --test scripts/具体测试文件.cjs` 定向复现。检查命令不得自动改文件；修复格式时只作用于本次负责的文件，随后再执行不带 `--fix` 的检查。若本机 pnpm 脚本在启动器解析目录时失败，可在相同工作目录分别使用 `pnpm exec vue-tsc --noEmit --skipLibCheck`、`pnpm exec eslint src --max-warnings 0`、`pnpm exec node scripts/run-contract-tests.cjs` 运行同一检查，并记录环境差异。

## 后端与契约

在 `backend/` 执行隔离验证：

```powershell
python -m poetry run python manage.py check --settings=devops.test_full_settings
python -m poetry run python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings
python -m poetry run pytest --ds=devops.test_full_settings
```

- Serializer 使用显式字段白名单；关联对象、角色权限与数据范围单独授权，不能允许调用者透传 Django 特权字段。
- 创建、克隆、定时触发、重试和 Worker 执行使用统一授权服务，执行前按当时的活跃用户与角色重新核验。
- 异步完成、失败、控制台、心跳与主机结果使用原 attempt/task 或回读 token/state 代次围栏；迟到任务不能推进当前投影。
- 任务单和定时定义的秘密值加密存储，响应脱敏，编辑沿用保留原值协议；不要把秘密放入事件、审计、测试快照或 URL query。
- 运行、节点、attempt、主机结果与日志共享相同的数据可见范围；维护权限必须写负向测试。
- JSON 复杂模块参数先按 JSON 编码，再按既定 token 规则转义；前后端均须验证数组、对象、空结构和引号行为。
- 调度与界面时间遵循已有 `Asia/Shanghai`、`USE_TZ=False` 契约；涉及内部 UTC 锚点的代码必须说明转换边界，不能直接拼接 `Z`。

新增迁移、OpenAPI 变更和跨进程协议需要随实现更新。模型差异检查不等于目标 MySQL 升级验收；不可逆数据迁移必须说明备份、密钥与恢复方式。

## 提交与交接

提交信息使用 `type(scope): 中文 subject`。仓库钩子可能执行前端 typecheck/lint 和提交信息检查；不要绕过失败的检查，也不要为通过钩子改写无关文件。

交接说明写清问题触发条件、最终行为、测试命令与实际结果，以及未做的环境验收。测试失败、未运行和跳过应分开列；不得把历史通过数累加成当前结果。提交或 PR 不应包含真实密码、访问令牌、生产配置或私有 state。

上线前核对 [当前状态](backend/docs/current-status.md)、[本轮升级说明](backend/docs/2026-10-23-remediation.md) 与 [安全恢复手册](backend/docs/security-and-recovery-runbook.md)。
