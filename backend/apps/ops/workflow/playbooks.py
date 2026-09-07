def build_linux_shell_playbook(command_content):
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [
                {
                    "name": "Run shell command",
                    "ansible.builtin.shell": "{{ command_content }}",
                    "args": {"executable": "/bin/bash"},
                    "register": "command_result",
                }
            ],
        }
    ]


def build_windows_powershell_playbook(command_content):
    return [
        {
            "hosts": "all",
            "gather_facts": False,
            "tasks": [
                {
                    "name": "Run PowerShell command",
                    "ansible.windows.win_shell": "{{ command_content }}",
                    "register": "command_result",
                }
            ],
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
    if command_type == "linux_shell":
        return build_linux_shell_playbook(command_version.content)
    if command_type == "windows_powershell":
        return build_windows_powershell_playbook(command_version.content)
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
        module_name = extra_vars.get("module_name", command_version.content)
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
