"""Validate a workflow failure alert without exposing channel secrets."""

from rest_framework import serializers

from .models import NotificationTemplate


def validate_failure_alert(value):
    if value in ({}, None):
        return value
    if not isinstance(value, dict) or set(value) - {"templateId", "receivers"}:
        raise serializers.ValidationError("告警配置只支持通知模板和接收人")
    template_id = value.get("templateId")
    if type(template_id) is not int or template_id < 1:
        raise serializers.ValidationError("请选择有效的通知模板")
    template = NotificationTemplate.objects.filter(
        pk=template_id, is_active=True, channel__is_active=True
    ).first()
    if template is None:
        raise serializers.ValidationError("通知模板或渠道不存在或已停用")
    receivers = value.get("receivers", "")
    if not isinstance(receivers, str) or len(receivers) > 1024:
        raise serializers.ValidationError("接收人必须是最多 1024 字的文本")
    return {"templateId": template_id, "receivers": receivers.strip()}


def freeze_failure_alert(value):
    """Freeze message content for a run; channel credentials remain outside its snapshot."""
    if (
        not isinstance(value, dict)
        or not value.get("templateId")
        or value.get("templateSnapshot")
    ):
        return value
    template = NotificationTemplate.objects.filter(pk=value["templateId"]).first()
    if template is None:
        return value
    return {
        **value,
        "templateSnapshot": {
            "channelId": template.channel_id,
            "subjectTemplate": template.subject_template,
            "bodyTemplate": template.body_template,
            "receiverTemplate": template.receiver_template,
        },
    }
