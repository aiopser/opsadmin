from .module_fields import module_name_for, parameter_docs_for
from .models import (
    ApiEndpoint,
    CommandAtom,
    CommandVersion,
    JenkinsJob,
    NotificationTemplate,
)


NODE_RESOURCE_TYPES = (
    ("command", "命令", "command_version", "AutomationCommandResources"),
    ("script", "脚本", "command_version", "AutomationScriptResources"),
    ("playbook", "Playbook", "command_version", "AutomationPlaybookResources"),
    ("module", "Module", "command_version", "AutomationModuleResources"),
    ("api", "API", "api_endpoint", "AutomationApiResources"),
    ("jenkins", "Jenkins Job", "jenkins_job", "AutomationJenkinsResources"),
    ("notify", "通知", "notification_template", "AutomationNotificationResources"),
)


def _ansible_resources(node_type):
    return [
        {
            "id": item.id,
            "resourceKey": f"command_version:{item.id}",
            "nodeType": node_type,
            "resourceType": "command_version",
            "name": item.command.name,
            "code": item.command.code,
            "description": item.command.description,
            "version": item.version,
            "riskLevel": item.command.risk_level,
            "timeoutSeconds": item.timeout_seconds,
            "argumentSchema": item.argument_schema,
            "moduleName": module_name_for(item) if node_type == "module" else "",
            "parameterDocs": parameter_docs_for(item) if node_type == "module" else [],
            "defaultVars": item.default_vars,
            "checkModeSupported": item.check_mode_supported,
            "becomeEnabled": item.become_enabled,
        }
        for item in CommandVersion.objects.select_related("command")
        .filter(
            status=CommandVersion.Status.PUBLISHED,
            command__status=CommandAtom.Status.PUBLISHED,
            command__resource_kind=node_type,
        )
        .order_by("command__name", "-version", "id")
    ]


def node_resources(node_type):
    if node_type in CommandAtom.ResourceKind.values:
        return _ansible_resources(node_type)
    if node_type == "api":
        return [
            {
                "id": item.id,
                "resourceKey": f"api_endpoint:{item.id}",
                "nodeType": node_type,
                "resourceType": "api_endpoint",
                "name": item.name,
                "description": item.description,
                "summary": f"{item.method} {item.url}",
                "timeoutSeconds": item.timeout_seconds,
            }
            for item in ApiEndpoint.objects.filter(is_active=True).order_by(
                "name", "id"
            )
        ]
    if node_type == "jenkins":
        return [
            {
                "id": item.id,
                "resourceKey": f"jenkins_job:{item.id}",
                "nodeType": node_type,
                "resourceType": "jenkins_job",
                "name": item.name,
                "description": item.server.name,
                "summary": item.url or item.server.base_url,
                "argumentSchema": item.parameters,
            }
            for item in JenkinsJob.objects.select_related("server")
            .filter(is_active=True, server__is_active=True)
            .order_by("server__name", "name", "id")
        ]
    if node_type == "notify":
        return [
            {
                "id": item.id,
                "resourceKey": f"notification_template:{item.id}",
                "nodeType": node_type,
                "resourceType": "notification_template",
                "name": item.name,
                "description": item.channel.name,
                "summary": item.channel.get_channel_type_display(),
            }
            for item in NotificationTemplate.objects.select_related("channel")
            .filter(is_active=True, channel__is_active=True)
            .order_by("name", "id")
        ]
    return []


def node_resource_catalog(selected_type=""):
    resources_by_type = {
        node_type: node_resources(node_type) for node_type, *_ in NODE_RESOURCE_TYPES
    }
    types = [
        {
            "nodeType": node_type,
            "name": name,
            "resourceType": resource_type,
            "requiresResource": True,
            "resourceCount": len(resources_by_type[node_type]),
            "createRoute": create_route,
            "createRouteQuery": (
                {"kind": node_type}
                if node_type in CommandAtom.ResourceKind.values
                else {}
            ),
        }
        for node_type, name, resource_type, create_route in NODE_RESOURCE_TYPES
    ]
    return {
        "types": types,
        "resources": resources_by_type.get(selected_type, []) if selected_type else [],
    }
