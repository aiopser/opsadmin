from apps.automation.module_fields import module_name_for


# 平台保留的 extra_vars key 不注入 shell 环境（与 plan_builder.INTERNAL_INPUT_VAR_KEYS
# 及 validate_ansible_extra_vars 的保留清单对齐），防止内部协议变量泄漏到脚本进程。
SHELL_ENV_EXCLUDED_KEYS = frozenset(
    {
        "command_content",
        "module_name",
        "module_args",
        "playbook_content",
        "playbook",
        "execution_source",
        "source_command_version_id",
        "source_module_version_id",
        "risk_level",
        "playbook_id",
        "playbook_name",
        "module",
        "gateway_id",
        "host_strategy",
        "ansible_forks",
        "serial_batch",
        "max_fail_percentage",
        "extra_vars",
        "check_mode",
        "bypass_host_gateway",
        "python_executable",
    }
)


def shell_task_environment(extra_vars):
    """把标量 extra_vars 注入任务环境变量，脚本内 $var / $env:var 直接可用。

    资源默认变量、任务单参数、步骤映射结果从此符合 shell 传参常识；
    嵌套结构（dict/list）无法映射为环境变量，自动剔除。
    """
    env = {}
    for key, value in (extra_vars or {}).items():
        if key in SHELL_ENV_EXCLUDED_KEYS:
            continue
        if isinstance(value, (bool, str, int, float)):
            env[key] = str(value)
    return env


def build_linux_shell_playbook(command_content, environment=None):
    # 正文必须内联进任务：Ansible 渲染任务参数时会对正文做一次模板求值，
    # 脚本里的 {{ 变量 }} 由 extra_vars 提供值（与 playbook 节点行为一致）。
    # 若经 "{{ command_content }}" 变量注入，Ansible 不做递归渲染，
    # 正文中的 {{ }} 会被原样交给 shell。
    task = {
        "name": "Run shell command",
        "ansible.builtin.shell": command_content,
        "args": {"executable": "/bin/bash"},
        "register": "command_result",
    }
    if environment:
        task["environment"] = environment
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [task],
        }
    ]


def build_windows_powershell_playbook(command_content, environment=None):
    # 内联原因同 build_linux_shell_playbook；PowerShell 内用 $env:变量名 读取
    task = {
        "name": "Run PowerShell command",
        "ansible.windows.win_shell": command_content,
        "register": "command_result",
    }
    if environment:
        task["environment"] = environment
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [task],
        }
    ]


def build_python_playbook(command_content, python_executable=None):
    executable = python_executable or "{{ python_executable | default('python3') }}"
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [
                {
                    "name": "Write Python script",
                    "ansible.builtin.copy": {
                        "dest": "/tmp/devops_runner_script.py",
                        "content": "{{ command_content }}",
                        "mode": "0700",
                    },
                },
                {
                    "name": "Run Python script",
                    "ansible.builtin.shell": f"{executable} /tmp/devops_runner_script.py",
                    "register": "command_result",
                },
            ],
        }
    ]


def build_target_http_playbook(method, url):
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [
                {
                    "name": "Run HTTP request from target",
                    "ansible.builtin.uri": {
                        "method": method,
                        "url": url,
                    },
                    "register": "command_result",
                }
            ],
        }
    ]


def build_playbook(command_version, extra_vars=None):
    extra_vars = extra_vars or {}
    command_type = command_version.command_type
    # shell / win_shell 正文取 wrap 后的 command_content（含输出分段标记）内联进任务，
    # 同时把标量 extra_vars 注入环境变量（脚本里 $var 直接可用）
    inline_content = extra_vars.get("command_content", command_version.content)
    environment = shell_task_environment(extra_vars)
    if command_type == "linux_shell":
        return build_linux_shell_playbook(inline_content, environment)
    if command_type == "windows_powershell":
        return build_windows_powershell_playbook(inline_content, environment)
    if command_type == "python":
        return build_python_playbook(
            command_version.content,
            python_executable=extra_vars.get("python_executable"),
        )
    if command_type == "http_request":
        return build_target_http_playbook(
            extra_vars.get("method", "GET"),
            extra_vars.get("url", command_version.content),
        )
    if command_type == "playbook":
        return extra_vars.get("playbook", [])
    if command_type == "ansible_module":
        module_name = extra_vars.get("module_name", module_name_for(command_version))
        module_args = extra_vars.get("module_args", {})
        return [
            {
                "hosts": "all",
                "gather_facts": False,
                "tasks": [
                    {
                        "name": f"Run Ansible module {module_name}",
                        module_name: module_args,
                        "register": "command_result",
                    }
                ],
            }
        ]
    raise ValueError(f"Unsupported command type: {command_type}")
