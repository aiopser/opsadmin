# Module 独立字段与升级说明

## 字段职责

同一张 `automation_command_version` 版本表：

| 字段 | 用途 |
| --- | --- |
| content | 脚本正文或 Playbook YAML；新 Module 版本为空 |
| module_name | Module 名称，例如 ansible.builtin.service |
| parameter_docs | Module 参数说明列表，例如 [{"name":"name","description":"服务名称"}] |
| argument_schema | 原有参数校验规则；新 Module 版本为空对象 |
| default_vars | 脚本、Playbook 默认额外变量；新 Module 说明版本为空对象 |

前端 API 使用 `moduleName` / `parameterDocs`，请求与响应适配层只转换顶层字段名。数据库和冻结图使用 snake_case。

## 数据迁移 0012_module_fields

- 新增 module_name、parameter_docs；content 允许空值（空字符串，不是 NULL）。
- 将历史 Module 的 content 复制到 module_name，将旧说明（x-module-parameter-docs、properties 或扁平参数定义）复制到 parameter_docs。
- 保留历史 content、argument_schema、默认值以及发布信息作为兼容依据；不会改写已发布流程图、哈希和已有运行快照。
- 新 API 写入只使用独立字段；兼容旧请求的 content/argument_schema 输入并转换到新字段。新版本不再携带隐藏执行默认值。
- 旧快照没有 module_name 时，执行适配器回退旧 content。执行不得转而查询资源当前版本。
- 反向迁移会先把新版本的模块名和说明补回旧字段，再删除新列，避免回退时丢失新版本的定义。

## 部署

先备份数据库；在 backend/ 下执行：

```text
poetry run python manage.py migrate
```

完成迁移后，同批更新前端、API 与 Celery Worker。新代码依赖新列，不应在迁移前启动。旧客户端的读取视图无法识别只有新字段的 Module，因此不建议前后端分批长时间运行。

## 验收

1. 新建 Module，仅填写模块名和 key-value 参数说明；保存后 module_name、parameter_docs 有值，content、argument_schema 为空。
2. 保存脚本或 Playbook，正文仍完整保存在 content，两个 Module 专用字段为空。
3. 已有发布版本与归档版本迁移后可查看说明；旧执行默认值和历史运行保持兼容。
4. 发布新流程版本，其冻结图包含 Module 专用字段；Module 正文为空仍正确构造对应模块任务。
5. 快速执行选择新版本能显示参数说明，实际参数在本次执行填写；旧冻结图只有 content 时仍可构造相同任务。
6. 新旧字段冲突、空模块名、重复参数名或缺少说明均被接口拒绝。

此说明不表示已连接部署数据库或执行过真实主机任务；实际升级须在部署环境执行迁移并验收。
