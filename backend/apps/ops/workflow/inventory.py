import json
import re

from apps.ops.adapters import CredentialProvider


def inventory_hostname(host):
    """Return a stable, INI-safe and unique Ansible inventory host name."""
    raw_name = str(host.get("hostname") or "host")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name).strip("_.-") or "host"
    host_id = host.get("host_id")
    return f"{safe_name}__{host_id}" if host_id is not None else safe_name


def _inventory_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _host_line(host, credential_provider):
    hostname = host.get("inventory_hostname") or inventory_hostname(host)
    ip = host["address"]
    port = host["port"]
    parts = [hostname, f"ansible_host={ip}"]
    if port:
        parts.append(f"ansible_port={port}")
    variables = dict(host.get("variables") or {})
    variables["ansible_connection"] = host["connection_type"]
    credential_ref_id = host.get("credential_ref_id")
    if credential_ref_id:
        variables.update(credential_provider.resolve(credential_ref_id))
    for key, value in variables.items():
        if value is not None and value != "":
            parts.append(f"{key}={_inventory_value(value)}")
    return " ".join(parts)


def build_inventory(host_snapshots, group_vars=None, *, credential_provider: CredentialProvider):
    """Build an INI inventory; credential resolution is injected by the caller."""
    linux_hosts = []
    windows_hosts = []
    for host in host_snapshots:
        os_family = "windows" if host["connection_type"] == "winrm" else "linux"
        if os_family == "windows":
            windows_hosts.append(host)
        else:
            linux_hosts.append(host)

    lines = []
    if linux_hosts:
        lines.append("[linux]")
        lines.extend(_host_line(host, credential_provider) for host in linux_hosts)
        lines.append("")
        lines.append("[linux:vars]")
        lines.append("ansible_connection=ssh")
        lines.append("")

    if windows_hosts:
        lines.append("[windows]")
        lines.extend(_host_line(host, credential_provider) for host in windows_hosts)
        lines.append("")
        lines.append("[windows:vars]")
        lines.append("ansible_connection=winrm")
        lines.append("ansible_shell_type=powershell")
        lines.append("ansible_winrm_transport=ntlm")
        lines.append("ansible_winrm_server_cert_validation=ignore")
        lines.append("")

    if group_vars:
        lines.append("[all:vars]")
        for key, value in group_vars.items():
            lines.append(f"{key}={_inventory_value(value)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
