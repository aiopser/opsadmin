from django.db import migrations, models


def reject_unmapped_global_alerts(apps, schema_editor):
    template = apps.get_model("automation", "NotificationTemplate")
    enabled = list(
        template.objects.filter(alert_on_run_failure=True)
        .order_by("pk")
        .values_list("code", flat=True)[:20]
    )
    if enabled:
        raise RuntimeError(
            "仍有启用的全局失败告警模板（最多展示 20 个）：" + "、".join(enabled) + "。旧全局规则无法无损转换为流程/任务单规则。"
            "请先记录这些模板、在旧版本中关闭全局开关，再执行迁移并逐项配置流程告警。"
        )


class Migration(migrations.Migration):
    dependencies = [("automation", "0007_notification_alerts")]

    operations = [
        migrations.AddField(
            model_name="workflowtemplate",
            name="failure_alert",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(reject_unmapped_global_alerts, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="notificationtemplate", name="alert_on_run_failure"
        ),
    ]
