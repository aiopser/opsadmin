"""临时脚本：验证 hostCount、business/service_node__in 过滤与 PATCH。"""

import json
import urllib.error
import urllib.request

BASE = "http://192.168.12.26:8001/api/v1"


def request(method: str, path: str, token: str | None = None, payload: dict | None = None):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(req, data) as resp:
        return json.loads(resp.read()).get("data")


def main() -> None:
    token = request("POST", "/auth/login", payload={"username": "admin", "password": "123456"})["access"]

    nodes = request("GET", "/cmdb/service-tree-nodes?pageNum=1&pageSize=100", token).get("list", [])
    print("nodes:", json.dumps(
        [{"id": n["id"], "name": n["name"], "type": n["node_type"], "hostCount": n.get("hostCount")} for n in nodes],
        ensure_ascii=False))

    businesses = request("GET", "/cmdb/businesses?pageNum=1&pageSize=100", token).get("list", [])
    print("businesses:", json.dumps(
        [{"id": b["id"], "name": b["name"], "hostCount": b.get("hostCount")} for b in businesses],
        ensure_ascii=False))

    by_business = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100&business=2", token)
    print("hosts business=2:", by_business.get("total"))

    by_subtree = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100&service_node__in=2,3,4", token)
    print("hosts service_node__in=2,3,4:", by_subtree.get("total"),
          [h["hostname"] for h in by_subtree.get("list", [])])

    hosts = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100", token).get("list", [])
    order_host = next(h for h in hosts if h["hostname"] == "order-01")
    patched = request("PATCH", f"/cmdb/hosts/{order_host['id']}", token, {"service_node": 3})
    print("patch order-01 -> node3:", patched.get("serviceNodeName"))

    empty_in = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100&service_node__in=", token)
    print("hosts service_node__in= (empty):", empty_in.get("total"))

    # 还原演示数据：order-01 移回「订单服务」
    hosts = request("GET", "/cmdb/hosts?pageNum=1&pageSize=100", token).get("list", [])
    order_host = next(h for h in hosts if h["hostname"] == "order-01")
    restored = request("PATCH", f"/cmdb/hosts/{order_host['id']}", token, {"service_node": 4})
    print("restore order-01 -> node4:", restored.get("serviceNodeName"))


if __name__ == "__main__":
    main()
