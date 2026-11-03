# 开发规范与自动检查

本项目的自动检查入口为根目录 `.github/workflows/quality.yml`。推送、Pull Request 和手动触发均运行前后端两个独立任务；失败会阻断检查，不自动改写源码或锁文件。GitHub 分支保护需由仓库管理员将这两个任务设为必需检查。

## 环境与依赖

- 后端：Python 3.12、Poetry 2.4.1，先执行 `poetry check --lock`，再按 `backend/poetry.lock` 安装 main/dev 依赖；依赖变更同时提交 `pyproject.toml` 与锁文件。
- 前端：CI 使用 Node.js 22、pnpm 10.34.2，版本在 `frontend/package.json` 的 `packageManager` 固定；按 `pnpm-lock.yaml` 执行 `pnpm install --frozen-lockfile`。所有前端命令在 `frontend/` 下运行，只使用 pnpm。
- CI 使用 `devops.test_full_settings`：SQLite 内存数据库、内存 Celery/缓存/邮件/Channel Layer、独立临时运行目录。`DEVOPS_CONFIG_FILE=""` 明确禁止读取部署 INI；测试设置在导入基础设置前覆盖所有必需的虚构环境值，并禁用真实 Terraform 启动。无需部署数据库、Redis、凭据或云账号，不得将部署 INI、真实主机或通知目标作为测试依赖。

## 提交前命令

在 `backend/` 下执行：

```text
poetry check --lock
poetry run python -m unittest discover -s scripts -p 'test_*.py'
poetry run python scripts/check_python_format.py
poetry run python manage.py check --settings=devops.test_full_settings
poetry run python manage.py makemigrations --check --dry-run --noinput --settings=devops.test_full_settings
poetry run python manage.py migrate --noinput --settings=devops.test_full_settings
poetry run python manage.py spectacular --validate --fail-on-warn --settings=devops.test_full_settings --file schema.yml
poetry run python -m pytest -q --tb=short
```

`migrate` 验证从空库应用完整迁移图；后续 pytest 会再次为自己的隔离数据库应用完整迁移。不可用 `--no-migrations`、`--fake` 或减少测试发现规则代替交付验证。当前 CI 为 SQLite 检查；MySQL 锁、死锁、并发和升级行为需在明确隔离的 MySQL 环境验收，相关跳过不代表通过。

在 `frontend/` 下执行：

```text
pnpm lint
pnpm test:contracts
pnpm build
pnpm typecheck
```

`pnpm lint` 只读检查 `src/`，所有警告均视为失败。确需自动修复时由开发者显式执行 `pnpm lint:fix` 并审阅 diff。`pnpm test:contracts` 自动发现全部 `scripts/test-*.cjs`，通过 Node 测试运行器执行，新增契约脚本不需手工加入 CI。先构建再检查类型，确保路由生成结果也参与 `vue-tsc` 检查。

## 代码与接口约定

前端文件类型规则以根 `AGENTS.md` 和 `.agents/skills/` 为准：Vue 使用 `<script setup lang="ts">`、单根模板、既有组件与 UnoCSS；TS/JS 使用精确类型与小函数，不引入 `any` 或硬编码颜色。页面跳转使用后端菜单登记的路由名。异步资源响应须匹配当前资源身份与请求代次；保存成功快照必须来自提交时的载荷，不能把请求期间的新编辑标为已保存。

后端 serializer 使用显式字段白名单，敏感标志和角色授予独立授权。执行授权在 application 边界实施，并在异步执行前重验当前责任人的权限；视图检查不能替代应用服务检查。固定事务锁顺序，外部调用不应占用长事务；状态、输出和事件投影以原 attempt/task 身份进行条件提交，迟到任务不得覆盖当前代次或推动下游。

任务单、定时定义与运行输入中的秘密值加密保存，响应只提供脱敏值及明确的保留原值协议。秘密不得进入审计、异常或测试诊断；测试使用虚构值并拦截主机、云、Jenkins 和通知传输。API 请求、DTO 字段命名与错误协议保持一致；执行确认摘要用于校验配置，HTTP 幂等键单独绑定操作者和载荷，不能互相代替。

Conventional Commits 格式为 `type(scope): 中文 subject`。禁止提交整仓自动格式化来掩盖业务变更。后端门禁 `scripts/check_python_format.py` 实际使用锁定的 Black 检查 `apps/`、`common/`、`devops/`、`scripts/` 的生产 Python；迁移、测试文件和缓存不纳入该格式基线。语法错误始终拒绝；需要格式化的存量文件仅在其内容的 SHA-256 与 `python-format-baseline.json` 完全一致时豁免。哈希统一 LF 换行，避免 Windows/Linux 检出差异。新增文件或存量文件一旦改动，必须符合 Black 格式才能通过。

基线表示已知格式欠账，不代表全仓 Black 通过。后续按文件分批格式化并审阅 diff，并从基线删除已合规文件；Black 版本升级也需连同基线审阅。`poetry run python scripts/check_python_format.py --write-baseline` 仅供维护者在确认基线变更时使用，不应作为修复 CI 的自动步骤。CI 自动发现全部 `scripts/test_*.py` 独立回归，当前包括 7 项格式门禁测试与 1 项测试设置隔离测试，覆盖哈希失配、增量合规、CRLF、非法语法，以及测试设置导入时不读取部署 INI。

## 验证边界

GitHub Actions 下载、冷缓存依赖安装、Node.js 22 的 Linux 构建，以及仓库分支保护是否生效，须以实际远端运行结果确认。本地已有依赖上的通过记录不能代替这些结果。SQLite/mock 回归也不覆盖真实 Worker 失联、Runner、Jenkins 远端停止、云账号权限或浏览器交互验收。

OpenAPI 已纳入严格检查。10 月 23 日初测曾出现 56 条 warning（21 类）、131 条 error（25 类），且 `--validate` 仍退出 0；10 月 24 日补齐自定义 APIView 的精确请求/响应 DTO、计算字段类型、路径参数、匿名组件与枚举名称后，`--validate --fail-on-warn` 已实际通过，无错误或告警。未删除或排除接口，也未用全局自由对象代替缺失 DTO。

`backend/schema.yml` 是从当前 Django 路由、serializer 和 `extend_schema` 声明生成的静态接口快照；上述命令用于人工同步该文件。CI 严格生成到临时文件并与已提交快照比较，漂移即失败；`SORT_OPERATIONS=True` 保证独立进程生成顺序一致。响应 envelope 的真实字段为字符串 `code`、业务 `data` 和可空 `msg`。静态 schema 仅用于契约与客户端，不作为运行时鉴权依据，权限仍由 API 和应用服务执行。

Action 参数以官方文档为准：[setup-node](https://github.com/actions/setup-node)、[setup-python](https://github.com/actions/setup-python)、[pnpm action-setup](https://github.com/pnpm/action-setup)。
