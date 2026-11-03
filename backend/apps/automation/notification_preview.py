"""Notification variable catalogue and synthetic contexts; never load run secrets."""

from copy import deepcopy
import json

from jinja2 import TemplateError


SCENARIOS = ("failure", "workflow", "asset_sync", "provisioning", "security")


def _fields(schema):
    if isinstance(schema, list):
        return [item for item in schema if isinstance(item, dict) and item.get("name")]
    if isinstance(schema, dict):
        return _fields(schema.get("fields", []))
    return []


def _example(field):
    return {
        "number": 1,
        "integer": 1,
        "boolean": True,
        "multiselect": [],
        "array": [],
        "object": {},
    }.get(field.get("type"), "示例值")


def _sample_fields(schema):
    return {
        field["name"]: _example(field)
        for field in _fields(schema)
        if field.get("type") != "secret"
    }


def _node_outputs(node):
    command = node.get("commandVersion") or {}
    resource = (node.get("resourceSnapshot") or {}).get("definition") or {}
    return {
        **_sample_fields(node.get("outputSchema")),
        **_sample_fields(command.get("output_extractors")),
        **_sample_fields(resource.get("output_extractors")),
    }


def _sample_context(scenario, graph=None):
    if scenario not in SCENARIOS:
        raise ValueError("请选择有效的通知使用场景")
    if scenario == "security":
        return {
            "title": "漏洞公告：示例公告",
            "advisory": {
                "id": "AVD-EXAMPLE",
                "title": "示例漏洞公告",
                "url": "https://avd.aliyun.com/",
                "severity": "unknown",
                "category": "示例组件",
                "published": "2026-10-28",
            },
        }
    if scenario == "provisioning":
        return {
            "title": "资源申请：示例主机",
            "delivery": {
                "requestId": 1001,
                "name": "示例主机",
                "phase": "inventory_failed",
                "region": "cn-shanghai",
                "message": "资源已创建，等待回读纳管（示例）",
            },
        }
    if scenario == "asset_sync":
        return {
            "title": "资产同步失败：示例云账号",
            "sync": {
                "id": 1001,
                "sourceName": "示例云账号",
                "status": "failed",
                "trigger": "scheduled",
                "errorMessage": "区域读取失败（示例，不代表真实同步故障）",
            },
        }
    if scenario == "failure":
        return {
            "title": "通知模板测试",
            "run": {
                "id": 1001,
                "name": "通知模板测试",
                "status": "failed",
                "failureReason": "这是一条测试通知，不代表真实任务失败",
                "failedStep": "测试步骤",
                "failedHosts": ["test-host-01"],
                "detailPath": "/task/run-detail/1001",
            },
        }
    if graph is None:
        graph = {
            "inputSchema": {"fields": [{"name": "service", "type": "string"}]},
            "nodes": [
                {
                    "id": "step_1",
                    "type": "command",
                    "outputSchema": [{"name": "result"}],
                }
            ],
        }
    return {
        "title": "流程通知：通知模板测试",
        "inputs": _sample_fields(graph.get("inputSchema")),
        "nodes": {
            str(node["id"]): {"status": "success", "outputs": _node_outputs(node)}
            for node in graph.get("nodes", [])
            if node.get("id") and node.get("type") not in {"start", "end"}
        },
        "system": {
            "workflow_run_id": 1001,
            "triggered_by_id": 1,
            "trigger_type": "manual",
        },
    }


def _merge(base, updates):
    return {
        **base,
        **{
            key: _merge(base[key], value)
            if isinstance(base.get(key), dict) and isinstance(value, dict)
            else deepcopy(value)
            for key, value in updates.items()
        },
    }


def notification_context(scenario, sample_context=None, graph=None):
    base = _sample_context(scenario, graph)
    updates = sample_context if sample_context is not None else {}
    if not isinstance(updates, dict):
        raise ValueError("测试数据必须是 JSON 对象")
    unknown = set(updates) - set(base)
    if unknown:
        raise ValueError(f"当前场景不支持变量：{', '.join(sorted(unknown))}")
    if graph and scenario == "workflow":
        secret_names = {
            field["name"]
            for field in _fields(graph.get("inputSchema"))
            if field.get("type") == "secret"
        }
        if isinstance(updates.get("inputs"), dict) and secret_names.intersection(
            updates["inputs"]
        ):
            raise ValueError("测试数据不得包含流程秘密参数")
    for key, value in updates.items():
        if isinstance(base[key], dict) and not isinstance(value, dict):
            raise ValueError(f"{key} 必须是 JSON 对象")
    return _merge(base, updates)


def notification_catalog(scenario, graph=None):
    sample = _sample_context(scenario, graph)
    variables = []

    def add(expression, label, example, source):
        variables.append(
            {
                "expression": "{{ " + expression + " }}",
                "label": label,
                "example": example,
                "source": source,
            }
        )

    if scenario == "security":
        add("title", "系统生成的通知标题", sample["title"], "系统内置")
        labels = {
            "id": "公告编号",
            "title": "公告标题",
            "url": "公告链接",
            "severity": "严重程度（unknown 表示未评级）",
            "category": "公告分类",
            "published": "公告日期",
        }
        for key, value in sample["advisory"].items():
            add(f"advisory.{key}", labels[key], value, "系统内置")
    elif scenario == "provisioning":
        add("title", "资源申请通知标题", sample["title"], "系统内置")
        labels = {
            "requestId": "申请编号",
            "name": "申请名称",
            "phase": "交付阶段",
            "region": "地域",
            "message": "处理结果",
        }
        for key, value in sample["delivery"].items():
            add(f"delivery.{key}", labels[key], value, "系统内置")
    elif scenario == "asset_sync":
        add("title", "系统生成的同步告警标题", sample["title"], "系统内置")
        labels = {
            "id": "同步记录编号",
            "sourceName": "云账号名称",
            "status": "同步结果",
            "trigger": "触发方式（manual/scheduled）",
            "errorMessage": "失败原因",
        }
        for key, value in sample["sync"].items():
            add(f"sync.{key}", labels[key], value, "系统内置")
    elif scenario == "failure":
        labels = {
            "id": "运行编号",
            "name": "运行名称",
            "status": "运行状态",
            "failureReason": "失败原因",
            "failedStep": "首个失败步骤",
            "failedHosts": "失败主机列表（最多20台）",
            "detailPath": "运行详情相对路径",
        }
        add("title", "系统生成的告警标题", sample["title"], "系统内置")
        for key, value in sample["run"].items():
            add(f"run.{key}", labels[key], value, "系统内置")
    else:
        node_names = {
            str(node["id"]): node.get("name") or str(node["id"])
            for node in (graph or {}).get("nodes", [])
            if node.get("id")
        }
        add("title", "系统生成的通知标题", sample["title"], "系统内置")
        for key, value in sample["inputs"].items():
            add(f"inputs[{json.dumps(key)}]", "任务单参数", value, "流程定义")
        for key, node in sample["nodes"].items():
            prefix = f"nodes[{json.dumps(key)}]"
            name = node_names.get(key, key)
            add(f"{prefix}.status", f"{name}：运行状态", node["status"], "步骤输出")
            add(f"{prefix}.outputs", f"{name}：全部输出", node["outputs"], "步骤输出")
            for name, value in node["outputs"].items():
                add(
                    f"{prefix}.outputs[{json.dumps(name)}]",
                    f"{node_names.get(key, key)}：{name}",
                    value,
                    "步骤输出",
                )
        for key, label in {
            "workflow_run_id": "本次运行编号",
            "triggered_by_id": "发起人编号",
            "trigger_type": "触发方式",
        }.items():
            add(f"system.{key}", label, sample["system"][key], "系统内置")
    return {"variables": variables, "sampleContext": sample}


def preview_notification(
    *, scenario, subject, body, receivers, sample_context=None, graph=None
):
    from apps.jobs.node_executors import render_value

    context = notification_context(scenario, sample_context, graph)
    result = {"valid": True, "errors": {}, "subject": "", "body": "", "receivers": ""}
    for field, key, template in (
        ("subjectTemplate", "subject", subject),
        ("bodyTemplate", "body", body),
        ("receiverTemplate", "receivers", receivers),
    ):
        try:
            result[key] = render_value(template, context)
        except TemplateError as exc:
            result["valid"] = False
            result["errors"][field] = f"模板变量或语法错误：{exc}"
    return result
