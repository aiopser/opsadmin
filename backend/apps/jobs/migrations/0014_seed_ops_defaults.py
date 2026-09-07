from django.db import migrations

DEFAULT_SECURITY_RULES = [
    {
        "pattern": "rm -rf /",
        "match_mode": "regex",
        "risk_level": "fatal",
        "description": "禁止删除根目录",
        "blocked_count": 23,
    },
    {
        "pattern": "mkfs",
        "match_mode": "contains",
        "risk_level": "fatal",
        "description": "禁止格式化磁盘",
        "blocked_count": 5,
    },
    {
        "pattern": "dd if=",
        "match_mode": "prefix",
        "risk_level": "fatal",
        "description": "禁止dd写盘操作",
        "blocked_count": 3,
    },
    {
        "pattern": "chmod 777",
        "match_mode": "contains",
        "risk_level": "high",
        "description": "禁止开放全部权限",
        "blocked_count": 45,
    },
    {
        "pattern": "cat /etc/shadow",
        "match_mode": "contains",
        "risk_level": "high",
        "description": "禁止读取密码文件",
        "blocked_count": 12,
    },
    {
        "pattern": r"(wget|curl).*\|\s*sh",
        "match_mode": "regex",
        "risk_level": "high",
        "description": "禁止下载并执行脚本",
        "blocked_count": 8,
    },
]

DEFAULT_PLAYBOOKS = [
    {
        "name": "deploy_nginx.yml",
        "description": "Nginx配置部署",
        "content": "---\n- name: Update Nginx configuration\n  hosts: lb-prod\n  become: yes\n  tasks:\n    - name: Copy nginx.conf\n      copy:\n        src: templates/nginx.conf.j2\n        dest: /etc/nginx/nginx.conf\n    - name: Reload nginx\n      service:\n        name: nginx\n        state: reloaded",
    },
    {
        "name": "restart_service.yml",
        "description": "服务重启",
        "content": "---\n- name: Restart application service\n  hosts: app-prod\n  become: yes\n  tasks:\n    - name: Restart app\n      systemd:\n        name: app-service\n        state: restarted",
    },
    {
        "name": "backup_database.yml",
        "description": "数据库备份",
        "content": "---\n- name: Backup database\n  hosts: db-prod\n  tasks:\n    - name: Dump database\n      shell: mysqldump -u root mydb > /backup/mydb.sql",
    },
]


def seed_defaults(apps, schema_editor):
    SecurityRule = apps.get_model("jobs", "SecurityRule")
    Playbook = apps.get_model("jobs", "Playbook")
    for rule in DEFAULT_SECURITY_RULES:
        SecurityRule.objects.get_or_create(
            pattern=rule["pattern"],
            defaults={**rule, "enabled": True},
        )
    for playbook in DEFAULT_PLAYBOOKS:
        Playbook.objects.get_or_create(name=playbook["name"], defaults=playbook)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0013_commandintercept_gateway_playbook_securityrule"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, noop),
    ]
