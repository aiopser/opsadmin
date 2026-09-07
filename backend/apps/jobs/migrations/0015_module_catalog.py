from django.core.validators import RegexValidator
from django.db import migrations, models


DEFAULT_MODULES = [
    {
        "value": "service",
        "label": "service - 服务管理",
        "group": "系统管理",
        "description": "管理系统服务。支持 start, stop, restart, reload, status 等操作。",
        "params": "name(服务名), state(目标状态), enabled(是否开机启动)",
        "default_args": "name=nginx state=restarted",
    },
    {
        "value": "systemd",
        "label": "systemd - Systemd管理",
        "group": "系统管理",
        "description": "管理 systemd 服务单元。",
        "params": "name(服务名), state(目标状态), daemon_reload(重载守护进程)",
        "default_args": "name=nginx state=restarted daemon_reload=yes",
    },
    {
        "value": "user",
        "label": "user - 用户管理",
        "group": "系统管理",
        "description": "管理系统用户账户。",
        "params": "name(用户名), state(状态), groups(用户组)",
        "default_args": "name=ops state=present",
    },
    {
        "value": "cron",
        "label": "cron - 定时任务",
        "group": "系统管理",
        "description": "管理 crontab 定时任务。",
        "params": "name(任务名), minute, hour, job(命令)",
        "default_args": "name=backup minute=0 hour=2 job=/usr/local/bin/backup.sh",
    },
    {
        "value": "copy",
        "label": "copy - 文件复制",
        "group": "文件管理",
        "description": "将文件复制到远程主机。",
        "params": "src(源路径), dest(目标路径), mode(权限)",
        "default_args": "src=/tmp/app.conf dest=/etc/app.conf mode=0644",
    },
    {
        "value": "file",
        "label": "file - 文件/目录管理",
        "group": "文件管理",
        "description": "管理文件、目录和符号链接。",
        "params": "path(路径), state(状态), mode(权限)",
        "default_args": "path=/data state=directory mode=0755",
    },
    {
        "value": "template",
        "label": "template - 模板渲染",
        "group": "文件管理",
        "description": "使用 Jinja2 渲染模板并部署。",
        "params": "src(模板路径), dest(目标路径)",
        "default_args": "src=/tmp/nginx.conf.j2 dest=/etc/nginx/nginx.conf",
    },
    {
        "value": "yum",
        "label": "yum - YUM包管理",
        "group": "包管理",
        "description": "使用 yum 管理软件包。",
        "params": "name(包名), state(present/absent/latest)",
        "default_args": "name=vim state=present",
    },
    {
        "value": "apt",
        "label": "apt - APT包管理",
        "group": "包管理",
        "description": "使用 apt 管理软件包。",
        "params": "name(包名), state(present/absent/latest)",
        "default_args": "name=vim state=present",
    },
    {
        "value": "pip",
        "label": "pip - Python包管理",
        "group": "包管理",
        "description": "使用 pip 管理 Python 包。",
        "params": "name(包名), version(版本), virtualenv(虚拟环境)",
        "default_args": "name=requests state=present",
    },
    {
        "value": "shell",
        "label": "shell - Shell命令",
        "group": "命令执行",
        "description": "在远程主机执行 Shell 命令。",
        "params": "free-form(命令内容)",
        "default_args": "df -h",
    },
    {
        "value": "command",
        "label": "command - 命令执行",
        "group": "命令执行",
        "description": "在远程主机执行命令（不经过 shell）。",
        "params": "free-form(命令内容)",
        "default_args": "uptime",
    },
    {
        "value": "script",
        "label": "script - 脚本执行",
        "group": "命令执行",
        "description": "将本地脚本传输到远程并执行。",
        "params": "free-form(脚本路径)",
        "default_args": "/tmp/setup.sh",
    },
]


def seed_modules(apps, schema_editor):
    ModuleCatalog = apps.get_model("jobs", "ModuleCatalog")
    for order, item in enumerate(DEFAULT_MODULES, start=1):
        ModuleCatalog.objects.get_or_create(
            value=item["value"],
            defaults={**item, "order": order, "is_system": True},
        )


class Migration(migrations.Migration):
    dependencies = [("jobs", "0014_seed_ops_defaults")]

    operations = [
        migrations.CreateModel(
            name="ModuleCatalog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "value",
                    models.CharField(
                        max_length=128,
                        unique=True,
                        validators=[
                            RegexValidator(
                                message="Module 标识只能包含字母、数字、点、下划线和短横线",
                                regex="^[A-Za-z0-9_.-]+$",
                            )
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=255)),
                ("group", models.CharField(default="其他", max_length=64)),
                ("description", models.TextField(blank=True, default="")),
                ("params", models.TextField(blank=True, default="")),
                ("default_args", models.TextField(blank=True, default="")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("is_system", models.BooleanField(default=False)),
            ],
            options={
                "db_table": "jobs_module_catalog",
                "ordering": ["group", "order", "value"],
            },
        ),
        migrations.RunPython(seed_modules, migrations.RunPython.noop),
    ]
