"""危险命令黑名单匹配与拦截服务。"""

from django.db import transaction
from django.db.models import F

from .models import CommandIntercept, SecurityRule


class CommandBlockedError(ValueError):
    """命令命中黑名单规则时抛出。"""

    def __init__(self, rule, message):
        self.rule = rule
        super().__init__(message)


def find_blocking_rule(command: str):
    """返回命中的第一条启用黑名单规则，未命中返回 None。"""
    if not command:
        return None
    for rule in SecurityRule.objects.filter(enabled=True):
        if rule.matches(command):
            return rule
    return None


def check_command(command: str, *, operator=None, target_desc: str = ""):
    """检查命令是否命中黑名单；命中则记录拦截事件并抛出 CommandBlockedError。"""
    rule = find_blocking_rule(command)
    if rule is None:
        return None
    with transaction.atomic():
        SecurityRule.objects.filter(id=rule.id).update(
            blocked_count=F("blocked_count") + 1
        )
        CommandIntercept.objects.create(
            operator=operator,
            command=command,
            target_desc=target_desc,
            rule=rule,
            hit_pattern=rule.pattern,
            risk_level=rule.risk_level,
        )
    raise CommandBlockedError(rule, f"命令命中危险黑名单规则「{rule.pattern}」，已拦截")
