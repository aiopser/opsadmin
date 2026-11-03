# V2 重构测试基线

> 历史记录：以下命令和结果属于当时版本。当前实现、验证矩阵与本轮结果统一见 [current-status.md](current-status.md)，请勿把本页旧失败数或通过数当作当前结论。

## P0 / T01 核验记录（2026-09-07，未通过阶段门槛）

- 工作目录：`D:/front/soybean-admin`，分支 `dev2`，普通 checkout。
- 基准提交：`fb7d1e36118630d1c7dbf11ad6610426ebba303e`。
- 开始时 `git status --short` 仅有 `?? backend/docs/`；保留用户已有计划。
- 执行计划实际路径：`backend/docs/2026-09-07-devops-refactor.md`。
- 仓库内未发现 AGENTS.md 或 CLAUDE.md。前端为现有 SoybeanAdmin ElementPlus，页面样板位于 `frontend/src/views/manage/user/index.vue` 和 `frontend/src/views/manage/role/index.vue`。
- Python 3.12.10；`poetry.exe` 启动器损坏，但 `python -m poetry --version` 返回 2.4.1。
- `poetry.lock` 格式 2.1，Python 约束 `^3.10`。未修改依赖及锁文件，未使用 `.test-deps`。

## 实际命令和结果

以下 Poetry 命令必须在 `backend` 目录执行。

| 命令 | 实际结果 |
| --- | --- |
| `python -m poetry check` | 成功；5 条旧 `[tool.poetry]` 元数据弃用警告 |
| `python -m poetry env info` | 原 Poetry 缓存环境 Python 3.12.10，Valid 为 True |
| `python -m poetry run python -c "...find_spec..."` | 原环境未安装 pytest、Django、cryptography |
| `python -m poetry run pytest --collect-only -q` | 退出 1，pytest 命令不存在；不是业务用例失败 |

以上是修改前结果。随后在项目内 `.venv` 按原锁文件完成 100 项依赖安装（退出 0），没有使用原缓存环境的业务依赖。虚拟环境创建首次长时间无进展，停止后重试成功。

复现环境（PowerShell，在 backend 目录）：

```powershell
$env:POETRY_VIRTUALENVS_IN_PROJECT = 'true'
$env:POETRY_CACHE_DIR = Join-Path $env:TEMP 'devops-v2-poetry-cache'
python -m poetry install --no-root --no-interaction
```

最终验证结果：

| 命令 | 实际结果 |
| --- | --- |
| `python -m poetry run pytest --collect-only -q` | 236 collected；完整 ID 清单见 test-collection-t01.txt |
| `python -m poetry run pytest -q --tb=short` | 221 passed，15 failed，6 warnings；另有 13 subtests passed，21.86 秒，退出 1 |
| `python -m poetry run pytest apps/audit_center apps/permission apps/user --ds=devops.test_settings -q --tb=no` | 基础配置 38 passed，9 failed，3 warnings，8.75 秒 |
| `python -m poetry run pytest apps/audit_center/test_test_environment.py -q --ds=devops.test_settings` | 2 passed；修改前这两个用例实际失败，分别为 broker 未隔离和缺少独立运行目录 |
| `python -m poetry run python manage.py check --settings=devops.test_full_settings` | System check identified no issues |
| `python -m poetry run python manage.py makemigrations --check --dry-run --settings=devops.test_full_settings` | No changes detected |
| `git diff --check` | 成功；仅 Git 提示 LF 将转为 CRLF |

SQLite 数据库测试经过 Django 测试库创建和迁移；不等同于 MySQL 迁移验证。没有屏蔽迁移、使用 --fake 或清空测试套件。

最终 15 项失败的初步分类（现有实现/测试契约问题，不宣称已定位全部根因）：

- automation 2 项：模板过滤预期 1 条得到 17 条；节点资源目录包含额外种子资源。需进一步区分筛选行为和种子隔离预期。
- jobs 网关 1 项：旧请求缺少当前必填 moduleVersionId，返回 400。
- permission 9 项：6 项菜单/权限种子预期不一致，3 项动态路由查找失败；基础配置同样复现这 9 项。
- jobs/ops 3 项：测试替身缺少 graph_snapshot、username；测试导入不存在的 _expression_is_true。
- 环境问题：原 Poetry 启动器损坏及缺依赖已绕过/解决；Python 3.12 上有 Django 3.2 相关弃用警告，依赖支持升级留给 T02。
- T01 配置缺陷：初始 app 未启用导致收集失败，启用 app 后未启用完整路由导致 5 项 404；补全测试专用 URLconf 后 3 项通过，另 2 项暴露上述真实断言失败。

没有修改生产模型、服务、旧测试断言或种子来掩盖基线失败。

## 静态测试清单

修改前 AST 统计共 13 个匹配文件、223 个 `test_` 函数；原 `python_files = ["test_*.py"]` 仅匹配其中 `apps/jobs/test_ops_api.py`。最终实际收集 236 项（含 2 项新增隔离测试）；继承测试方法等因素使实际收集数不等于 AST 函数数。

| 文件（相对 apps） | test_ 函数数 |
| --- | ---: |
| audit_center/tests.py | 2 |
| automation/tests.py | 17 |
| cmdb/tests.py | 11 |
| jobs/creation_governance_tests.py | 1 |
| jobs/event_types_tests.py | 2 |
| jobs/state_machine_tests.py | 5 |
| jobs/test_ops_api.py | 45 |
| jobs/tests.py | 77 |
| jobs/workflow_engine_tests.py | 6 |
| ops/tests.py | 10 |
| ops/workflow/adapters_tests.py | 4 |
| permission/tests.py | 43 |
| user/tests.py | 0 |

## 隔离边界及迁移核验

Git 分支不隔离外部服务。原 `devops.test_settings` 覆盖 SQLite 内存数据库、内存缓存和 Channel Layer，但仍继承运行配置中的 Celery broker/result backend、队列、定时任务及日志/归档目录。本次已覆盖为内存 broker/backend、独立队列名、空调度/路由、独立临时日志/媒体/归档目录、测试签名密钥及内存邮件。未启动默认 settings、Worker 或真实 Runner。

已静态读取全部项目迁移依赖。跨 app 依赖包括：user → permission/auth，audit_center → user，jobs → user/cmdb/automation/audit_center，automation → user/jobs，cmdb → jobs，permission → user。ops 当前 label 为 ansible_platform，其 0002 依赖该 label 的 0001。不得仅删除某一个 app 的迁移；模型归属调整后的迁移重建留在计划指定任务。

仅运行 SQLite 内存测试数据库；未连接外部数据库、Redis 或资产，未清空已有存储。MySQL 集成只能使用独立的新空库，且需明确隔离实例和库名；现有部署 INI 不能作为测试环境来源。

## 变更和删除清单

- `.gitignore`：忽略项目内 backend/.venv 和 pytest 缓存。
- `backend/pyproject.toml`：补全 tests.py、*_tests.py 的发现规则，默认采用全模块测试配置。
- `backend/devops/test_settings.py`：补齐内存服务、测试密钥与运行目录隔离。
- `backend/devops/test_full_settings.py`：新增全部业务 app 的 SQLite 测试设置。
- `backend/devops/test_full_urls.py`：仅测试环境启用现有 cmdb、automation、jobs 路由，部署路由未改动。
- `backend/apps/audit_center/test_test_environment.py`：新增两项隔离回归。
- `backend/docs/testing.md`、`backend/docs/test-collection-t01.txt`：核验记录与实际测试 ID 清单。
- 删除清单：无。未删除源码、测试、迁移、原附件或数据；未引入旧协议兼容层。

## 待完成

- 独立 MySQL 集成配置、明确的新空库和实际迁移验证尚未完成；不能把 SQLite 结果当作 MySQL 通过。
- 15 项基线失败尚未解决/签收；后续应按 V2 业务覆盖处理，不能恢复旧协议来满足旧测试。
- T01 未通过阶段门槛，未进入 T02 或后续阶段。

本次未删除业务代码、测试或迁移；未引入兼容层。T01 未完成，不作为阶段通过或本地完成提交。

回滚仅需恢复本次列出的配置及新增测试/文档；用户原有计划保留。业务代码基准仍为上述提交，没有需要回滚的外部数据变更。
