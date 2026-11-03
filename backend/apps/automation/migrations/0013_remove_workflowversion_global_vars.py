from django.db import migrations


class Migration(migrations.Migration):
    """移除「流程内置变量」概念：常量直接写在步骤参数映射或资源默认变量中。"""

    dependencies = [
        ("automation", "0012_module_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="workflowversion",
            name="global_vars",
        ),
    ]
