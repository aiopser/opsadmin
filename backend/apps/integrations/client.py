"""JumpServer v3/v4 HTTP Signature client; errors never expose upstream bodies."""
import base64
import hashlib
import hmac
import ipaddress
import socket
from email.utils import formatdate
from urllib.parse import urlsplit
import requests
from requests.adapters import HTTPAdapter
from apps.cmdb.crypto import decrypt_secret
from apps.consul.client import validate_endpoint, blocked_address


class JumpServerError(Exception):
    pass


class PinnedTLSAdapter(HTTPAdapter):
    """Connect to the validated IP while retaining certificate hostname and SNI."""

    def __init__(self, hostname):
        self.hostname = hostname
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            assert_hostname=self.hostname,
            server_hostname=self.hostname,
            **kwargs,
        )


def signature_headers(
    key_id, secret, date=None, method="GET", path="/api/v1/users/users/"
):
    date = date or formatdate(usegmt=True)
    signature = base64.b64encode(
        hmac.new(
            secret.encode(),
            f"(request-target): {method.lower()} {path}\naccept: application/json\ndate: {date}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    return {
        "Date": date,
        "Authorization": f'Signature keyId="{key_id}",algorithm="hmac-sha256",headers="(request-target) accept date",signature="{signature}"',
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


class JumpServerClient:
    def __init__(self, connection):
        self.connection = connection

    def request(self, method, path, payload=None):
        connection = self.connection
        try:
            endpoint = validate_endpoint(connection.endpoint)
            parsed = urlsplit(endpoint)
            addresses = socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            if not addresses:
                raise JumpServerError("JumpServer 地址无法解析")
            for item in addresses:
                if blocked_address(ipaddress.ip_address(item[4][0])):
                    raise JumpServerError("JumpServer 地址解析到禁止的网络地址")
            headers = signature_headers(
                connection.key_id,
                decrypt_secret(connection.secret_encrypted),
                method=method,
                path="/api/v1/" + path,
            )
            headers["Host"] = parsed.netloc
            address = addresses[0][4][0]
            address = f"[{address}]" if ":" in address else address
            pinned_endpoint = f'{parsed.scheme}://{address}:{parsed.port or (443 if parsed.scheme == "https" else 80)}'
            if connection.org_id:
                headers["X-JMS-ORG"] = connection.org_id
            with requests.Session() as session:
                session.trust_env = False
                if parsed.scheme == "https":
                    session.mount("https://", PinnedTLSAdapter(parsed.hostname))
                if payload and "platform" in payload:
                    payload = {
                        **payload,
                        "platform": {"pk": payload["platform"]},
                        "nodes": [{"pk": node} for node in payload["nodes"]],
                    }
                response = session.request(
                    method,
                    pinned_endpoint + "/api/v1/" + path,
                    json=payload,
                    headers=headers,
                    timeout=(3, 15),
                    verify=connection.verify_tls,
                    allow_redirects=False,
                )
            if response.status_code == 404 and method == "GET":
                return None
            if not 200 <= response.status_code < 300:
                raise JumpServerError(f"JumpServer 请求失败 (HTTP {response.status_code})")
            return response.json()
        except JumpServerError:
            raise
        except Exception:
            raise JumpServerError("JumpServer 网络、证书、凭据或响应格式错误") from None

    def test(self):
        result = self.request("GET", "assets/nodes/" + self.connection.node_id + "/")
        if not isinstance(result, dict):
            raise JumpServerError("JumpServer 目标节点不存在或返回格式错误")
        return result
