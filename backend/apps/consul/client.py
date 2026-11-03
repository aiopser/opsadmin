"""Bounded Consul Agent API; no caller-controlled paths or redirects."""
import ipaddress
import re
import socket
from base64 import b64decode
from urllib.parse import quote, urlsplit

import requests
from rest_framework.exceptions import ValidationError

from apps.cmdb.crypto import decrypt_secret


class ConsulError(Exception):
    pass


# KV 浏览与编辑：key 字符集收紧，读写响应限制大小，404 视为空结果
KV_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_./-]{0,512}$")
KV_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
KV_MAX_VALUE_BYTES = 1024 * 1024


def _entry_index(entry, name):
    """Consul KV 条目的 Raft 索引字段取整；缺失或类型异常时按 0 处理。"""
    value = entry.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def blocked_address(address):
    address = getattr(address, "ipv4_mapped", None) or address
    return (
        address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or str(address) in {"100.100.100.200", "fd00:ec2::254"}
    )


def validate_endpoint(value):
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise ValidationError("请输入合法的 Consul HTTP(S) 地址")
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValidationError("地址仅支持 HTTP(S) 主机和端口，不支持凭据、路径或查询参数")
    if url.hostname.lower() in {
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }:
        raise ValidationError("不允许访问云元数据地址")
    try:
        address = ipaddress.ip_address(url.hostname)
    except ValueError:
        address = None
    if address and blocked_address(address):
        raise ValidationError("不允许访问链路本地、未指定或组播地址")
    return value.rstrip("/")


class ConsulClient:
    def __init__(self, connection):
        self.connection = connection

    def _request(self, method, path, payload=None, params=None, data=None, allow_404=False, max_bytes=None):
        connection = self.connection
        if not connection.is_active:
            raise ConsulError("Consul 连接已停用")
        try:
            endpoint = validate_endpoint(connection.endpoint)
            host = urlsplit(endpoint).hostname
            for item in socket.getaddrinfo(
                host, urlsplit(endpoint).port or 8500, type=socket.SOCK_STREAM
            ):
                address = ipaddress.ip_address(item[4][0])
                if blocked_address(address):
                    raise ConsulError("Consul 地址解析到不允许访问的网络地址")
            token = decrypt_secret(connection.token_encrypted)
            session = requests.Session()
            session.trust_env = False
            try:
                response = session.request(
                    method,
                    endpoint + "/v1" + path,
                    headers={"X-Consul-Token": token} if token else {},
                    json=payload,
                    data=data,
                    params=params,
                    timeout=(3, 10),
                    allow_redirects=False,
                )
            finally:
                session.close()
            if response.status_code == 404 and allow_404:
                return None
            if max_bytes is not None and len(response.content) > max_bytes:
                raise ConsulError("Consul 响应内容超过大小限制")
            if not 200 <= response.status_code < 300:
                raise ConsulError(
                    f"Consul 请求失败（HTTP {response.status_code}），请检查 ACL 权限和连接配置"
                )
            if not response.content or not response.content.strip():
                return None
            return response.json()
        except ConsulError:
            raise
        except requests.Timeout:
            raise ConsulError("Consul 请求超时，请检查网络和服务状态") from None
        except (requests.RequestException, OSError):
            raise ConsulError("无法连接 Consul，请检查 DNS、网络、证书及服务地址") from None
        except Exception:
            raise ConsulError("Consul 凭据解密或响应解析失败，请检查配置与返回格式") from None

    def test_connection(self):
        result = self._request("GET", "/agent/self")
        if not isinstance(result, dict) or not isinstance(result.get("Config"), dict):
            raise ConsulError("Consul Agent 返回格式不正确")
        return {
            "agent": str(result["Config"].get("NodeName", "")),
            "datacenter": str(result["Config"].get("Datacenter", "")),
        }

    def agent_services(self):
        result = self._request("GET", "/agent/services")
        if not isinstance(result, dict) or not all(
            isinstance(item, dict) for item in result.values()
        ):
            raise ConsulError("Consul 服务列表返回格式不正确")
        return result

    def agent_checks(self):
        result = self._request("GET", "/agent/checks")
        if not isinstance(result, dict):
            raise ConsulError("Consul 健康检查返回格式不正确")
        return result

    def register(self, payload):
        self._request(
            "PUT", "/agent/service/register?replace-existing-checks=true", payload
        )

    def datacenters(self):
        result = self._request("GET", "/catalog/datacenters")
        if not isinstance(result, list) or not all(
            isinstance(item, str) for item in result
        ):
            raise ConsulError("Consul 数据中心列表格式不正确")
        return sorted(result)

    def catalog_services(self, datacenter=""):
        dc = datacenter or self.connection.datacenter
        result = self._request(
            "GET", "/catalog/services", params={"dc": dc} if dc else {}
        )
        if not isinstance(result, dict) or not all(
            isinstance(value, list) for value in result.values()
        ):
            raise ConsulError("Consul Catalog 服务列表格式不正确")
        return [{"name": name, "tags": tags} for name, tags in sorted(result.items())]

    def catalog_instances(self, service, datacenter=""):
        dc = datacenter or self.connection.datacenter
        result = self._request(
            "GET",
            "/health/service/" + quote(service, safe=""),
            params={"dc": dc} if dc else {},
        )
        if (
            not isinstance(result, list)
            or len(result) > 10000
            or not all(
                isinstance(item, dict)
                and isinstance(item.get("Service"), dict)
                and isinstance(item.get("Node"), dict)
                and isinstance(item.get("Checks"), list)
                for item in result
            )
        ):
            raise ConsulError("Consul Catalog 实例格式异常或数量超过 10000，请缩小服务范围")
        return result

    def deregister(self, service_id):
        self._request("PUT", "/agent/service/deregister/" + quote(service_id, safe=""))

    @staticmethod
    def _check_kv_key(key, allow_empty=False):
        """KV key 仅允许字母数字与 _ . - /，拒绝空段和相对路径段，防止路径穿越。"""
        if not key:
            if allow_empty:
                return ""
            raise ConsulError("KV Key 不能为空")
        if len(key) > 512 or not KV_KEY_PATTERN.fullmatch(key) or key.startswith("/"):
            raise ConsulError("KV Key 仅支持字母、数字与 _ - . / 字符，长度不超过 512")
        segments = key.rstrip("/").split("/")
        if not segments or any(segment in {"", ".", ".."} for segment in segments):
            raise ConsulError("KV Key 不允许空段或相对路径段")
        return key

    def kv_keys(self, prefix=""):
        """按层级列出 Key：?keys&separator=/ 返回该前缀下一层的 Key 与目录。"""
        key = self._check_kv_key(prefix, allow_empty=True)
        result = self._request(
            "GET", "/kv/" + quote(key, safe="") + "?keys&separator=%2F", allow_404=True
        )
        if not isinstance(result, list):
            return []
        keys = [item for item in result if isinstance(item, str)]
        return sorted(keys)[:10000]

    def kv_value(self, key):
        """读取单个 Key 的文本值（UTF-8）及版本元信息；目录或非文本内容不支持预览。"""
        key = self._check_kv_key(key)
        data = self._request(
            "GET",
            "/kv/" + quote(key.rstrip("/"), safe=""),
            allow_404=True,
            max_bytes=KV_MAX_RESPONSE_BYTES,
        )
        entry = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None
        if entry is None:
            raise ConsulError("KV 不存在或已被删除")
        raw = entry.get("Value")
        if not isinstance(raw, str):
            raise ConsulError("该 Key 没有值或值为空")
        try:
            text = b64decode(raw).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ConsulError("KV 值不是 UTF-8 文本，暂不支持预览") from None
        return {
            "key": str(entry.get("Key", key)),
            "value": text,
            "create_index": _entry_index(entry, "CreateIndex"),
            "modify_index": _entry_index(entry, "ModifyIndex"),
            "lock_index": _entry_index(entry, "LockIndex"),
            "flags": _entry_index(entry, "Flags"),
        }

    def kv_write(self, key, value):
        """写入单个 Key（PUT upsert，consul-template 会 watch 变更并热加载）。"""
        key = self._check_kv_key(key)
        if key.endswith("/"):
            raise ConsulError("不允许写入以 / 结尾的目录 Key")
        if not isinstance(value, str):
            raise ConsulError("KV 值必须是文本")
        if len(value.encode("utf-8")) > KV_MAX_VALUE_BYTES:
            raise ConsulError("KV 值超过 1MB 大小限制")
        result = self._request("PUT", "/kv/" + quote(key, safe=""), data=value)
        if result is not True:
            raise ConsulError("KV 写入失败，请检查 Consul ACL 写权限")
        return True

    def kv_delete(self, key):
        """删除单个 Key；目录形态的 Key 不允许删除，需逐个处理以控制误删影响面。"""
        key = self._check_kv_key(key)
        if key.endswith("/"):
            raise ConsulError("不允许删除以 / 结尾的目录，请逐个删除 Key")
        result = self._request("DELETE", "/kv/" + quote(key, safe=""))
        if result is not True:
            raise ConsulError("KV 删除失败，请检查 Consul ACL 写权限")
        return True
