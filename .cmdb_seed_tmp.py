"""临时脚本：为左树右表页面创建演示数据（业务/服务树节点/主机）。"""

import json
import urllib.request

BASE = "http://192.168.12.26:8001/api/v1"


def request(method: str, path: str, token: str | None = None, payload: dict | None = None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, data) as resp:
        body = json.loads(resp.read())
    if body.get("code") != "00000":
        raise RuntimeError(f"{method} {path} failed: {body}")
    return body.get("data")


def ensure_by_code(method_path: str, list_path: str, code: str, token: str, payload: dict) -> dict:
    """按 code 幂等创建：已存在则复用。"""
    existing = request("GET", list_path, token).get("list", [])
    found = next((item for item in existing if item.get("code") == code), None)
    if found:
        return found
    return request("POST", method_path, token, payload)


def main() -> None:
    token = request("POST", "/auth/login", payload={"username": "admin", "password": "123456"})["access"]

    business = ensure_by_code(
        "/cmdb/businesses", "/cmdb/businesses?pageNum=1&pageSize=100", "demo", token,
        {"code": "demo", "name": "演示业务", "description": "左树右表演示", "is_active": True},
    )
    env = ensure_by_code(
        "/cmdb/service-tree-nodes", "/cmdb/service-tree-nodes?pageNum=1&pageSize=100", "prod", token,
        {"business": business["id"], "parent": None, "code": "prod", "name": "生产环境",
         "node_type": "environment", "sort_order": 1, "is_active": True},
    )
    region = ensure_by_code(
        "/cmdb/service-tree-nodes", "/cmdb/service-tree-nodes?pageNum=1&pageSize=100", "cn-north", token,
        {"business": business["id"], "parent": env["id"], "code": "cn-north", "name": "华北区域",
         "node_type": "region", "sort_order": 1, "is_active": True},
    )
    module_core = ensure_by_code(
        "/cmdb/service-tree-nodes", "/cmdb/service-tree-nodes?pageNum=1&pageSize=100", "core", token,
        {"business": business["id"], "parent": region["id"], "code": "core", "name": "核心服务",
         "node_type": "module", "sort_order": 1, "is_active": True},
    )
    module_order = ensure_by_code(
        "/cmdb/service-tree-nodes", "/cmdb/service-tree-nodes?pageNum=1&pageSize=100", "order", token,
        {"business": business["id"], "parent": region["id"], "code": "order", "name": "订单服务",
         "node_type": "module", "sort_order": 2, "is_active": True},
    )

    hosts = [
        {"hostname": "web-01", "primary_ip": "10.0.1.11", "asset_type": "server", "os_family": "linux",
         "connection_type": "ssh", "connection_port": 22, "cpu_cores": 2,
         "memory_mb": 4096, "system_disk_gb": 40, "data_disk_gb": 100, "environment": "prod",
         "status": "active", "owner_team": "运维部", "app_code": "order",
         "service_node": module_core["id"]},
        {"hostname": "web-02", "primary_ip": "10.0.1.12", "asset_type": "server", "os_family": "linux",
         "connection_type": "ssh", "connection_port": 22, "cpu_cores": 4,
         "memory_mb": 8192, "system_disk_gb": 40, "data_disk_gb": 200, "environment": "prod",
         "status": "active", "owner_team": "运维部", "app_code": "order",
         "service_node": module_core["id"]},
        {"hostname": "order-01", "primary_ip": "10.0.1.21", "asset_type": "server", "os_family": "linux",
         "connection_type": "ssh", "connection_port": 22, "cpu_cores": 2,
         "memory_mb": 2048, "system_disk_gb": 40, "data_disk_gb": 50, "environment": "prod",
         "status": "inactive", "owner_team": "业务研发", "app_code": "order",
         "service_node": module_order["id"]},
        {"hostname": "win-01", "primary_ip": "10.0.1.31", "asset_type": "server", "os_family": "windows",
         "connection_type": "winrm", "connection_port": 5985, "cpu_cores": 8,
         "memory_mb": 16384, "system_disk_gb": 100, "data_disk_gb": 500, "environment": "prod",
         "status": "active", "owner_team": "运维部", "app_code": "report",
         "service_node": env["id"]},
    ]
    existing_hosts = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100", token).get("list", [])
    known_names = {item.get("hostname") for item in existing_hosts}
    for host in hosts:
        if host["hostname"] in known_names:
            continue
        request("POST", "/cmdb/hosts", token, host)

    print(json.dumps({
        "business": business["id"],
        "env": env["id"],
        "region": region["id"],
        "module_core": module_core["id"],
        "module_order": module_order["id"],
        "hosts": len(hosts),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
