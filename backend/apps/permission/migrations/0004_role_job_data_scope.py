from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("permission", "0003_menu_name_len64")]

    operations = [
        migrations.AddField(
            model_name="role",
            name="job_data_scope",
            field=models.CharField(
                max_length=16,
                choices=[
                    ("own", "本人作业"),
                    ("department", "同部门作业"),
                    ("all", "全部作业"),
                ],
                default="own",
                verbose_name="Job data scope",
                help_text="本人/同部门/全部作业的运行可见范围",
            ),
        ),
    ]
