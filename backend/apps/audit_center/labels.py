"""审计事件的展示标签，与前端 frontend/src/views/audit/event/shared.ts 保持一致。

前端负责渲染名称；后端用同一份标签把中文/英文关键词还原成
(action, resource_type) 组合，让关键词搜索与表格展示内容一致。
"""

RESOURCE_LABELS = {
    "workflow_run": ("执行记录", "Run"),
    "login": ("登录账号", "Login account"),
    "workflow_task_ticket": ("任务单", "Task ticket"),
    "workflow": ("流程", "Workflow"),
    "workflow_version": ("流程版本", "Workflow version"),
    "workflow_node": ("流程步骤", "Workflow step"),
    "workflow_edge": ("流程连接", "Workflow connection"),
    "command": ("命令", "Command"),
    "command_version": ("命令版本", "Command version"),
    "worker_pool": ("执行池", "Worker pool"),
    "host": ("主机资产", "Host asset"),
    "cmdb_host": ("主机资产", "Host asset"),
    "host_group": ("主机分组", "Host group"),
    "cmdb_host_group": ("主机分组", "Host group"),
    "tag": ("资产标签", "Asset tag"),
    "cmdb_host_tag": ("资产标签", "Asset tag"),
    "credential": ("凭据引用", "Credential reference"),
    "cmdb_credential_ref": ("凭据引用", "Credential reference"),
    "asset_source": ("资产来源", "Asset source"),
    "cmdb_asset_source": ("资产来源", "Asset source"),
    "api_endpoint": ("API 接口", "API endpoint"),
    "jenkins_server": ("Jenkins 服务", "Jenkins server"),
    "jenkins_job": ("Jenkins 作业", "Jenkins job"),
    "git_repository": ("Git 仓库", "Git repository"),
    "notification_channel": ("通知渠道", "Notification channel"),
    "notification_template": ("通知模板", "Notification template"),
}

ACTION_LABELS = {
    "auth.login.success": ("登录成功", "Login succeeded"),
    "auth.login.failure": ("登录失败", "Login failed"),
    "quick_command_run.create": ("执行快速命令", "Run quick command"),
    "playbook_run.create": ("执行剧本", "Run playbook"),
    "module_run.create": ("执行模块", "Run module"),
    "jobs.workflow_ticket.run": ("执行任务单", "Run task ticket"),
    "jobs.workflow_ticket.delete": ("删除任务单", "Delete task ticket"),
    "workflow_run.create": ("启动执行", "Start run"),
    "workflow_run.cancel": ("取消执行", "Cancel run"),
    "workflow_run.retry_failed": ("重试失败步骤", "Retry failed steps"),
    "workflow_run.rerun": ("重新执行", "Rerun"),
}

VERB_LABELS = {
    "create": ("创建", "Create"),
    "update": ("修改", "Update"),
    "delete": ("删除", "Delete"),
    "publish": ("发布", "Publish"),
    "run": ("执行", "Run"),
    "test_send": ("测试发送", "Test send"),
    "enable": ("启用", "Enable"),
    "disable": ("停用", "Disable"),
}


def _pair_labels(action, resource_type):
    """与前端 getAuditActionLabel 的解析顺序一致：精确动作名优先，其次动词 + 对象名。"""
    exact = ACTION_LABELS.get(action)
    if exact:
        return exact
    verb = VERB_LABELS.get(str(action).rsplit(".", 1)[-1])
    resource = RESOURCE_LABELS.get(resource_type)
    if verb and resource:
        return (f"{verb[0]}{resource[0]}", f"{verb[1]} {resource[1].lower()}")
    return ()


def match_event_pairs(pairs, keyword):
    """返回表格展示名命中关键词的 (action, resource_type) 组合。"""
    normalized = keyword.strip().casefold()
    if not normalized:
        return []
    return [
        (action, resource_type)
        for action, resource_type in pairs
        if any(normalized in label.casefold() for label in _pair_labels(action, resource_type))
    ]
