"""Shared workflow vocabulary, independent of Django and runtime models."""

from enum import StrEnum


class NodeType(StrEnum):
    START = "start"
    END = "end"
    COMMAND = "command"
    SCRIPT = "script"
    PLAYBOOK = "playbook"
    MODULE = "module"
    API = "api"
    JENKINS = "jenkins"
    NOTIFY = "notify"
    PARALLEL_GATEWAY = "parallel_gateway"
    PARALLEL_JOIN = "parallel_join"


NODE_CHOICES = tuple(
    (item.value, label)
    for item, label in (
        (NodeType.START, "Start"),
        (NodeType.END, "End"),
        (NodeType.COMMAND, "Command"),
        (NodeType.SCRIPT, "Script"),
        (NodeType.PLAYBOOK, "Playbook"),
        (NodeType.MODULE, "Ansible Module"),
        (NodeType.API, "API"),
        (NodeType.JENKINS, "Jenkins"),
        (NodeType.NOTIFY, "Notification"),
        (NodeType.PARALLEL_GATEWAY, "Parallel Gateway"),
        (NodeType.PARALLEL_JOIN, "Parallel Join"),
    )
)
ANSIBLE_NODE_TYPES = frozenset(
    {NodeType.COMMAND, NodeType.SCRIPT, NodeType.PLAYBOOK, NodeType.MODULE}
)
CONTROL_NODE_TYPES = frozenset(
    {NodeType.START, NodeType.END, NodeType.PARALLEL_GATEWAY, NodeType.PARALLEL_JOIN}
)
NODE_TYPES = frozenset(NodeType)
