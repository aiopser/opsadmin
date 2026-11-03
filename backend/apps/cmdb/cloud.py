"""Read-only cloud inventory collection. Credentials never enter host snapshots."""

import base64
import ipaddress
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from .crypto import decrypt_secret
from .cloud_diagnostics import cloud_probe_error
from .models import AssetSource
from .cloud_capabilities import cloud_state


MAX_ASSETS = 1000
PAGE_SIZE = 100
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class CloudCollectionError(ValueError):
    """Safe, user-facing collection validation error."""


def _validate_inventory(assets):
    if len(assets) > MAX_ASSETS:
        raise CloudCollectionError("云资产超过单次预览上限 1000 台，请缩小范围")
    seen = set()
    for item in assets:
        instance = str(item.get("source_id") or "").strip()
        if not instance or instance in seen:
            raise CloudCollectionError("云接口返回缺失或重复的实例 ID，本次未同步，请重新读取并检查区域范围")
        seen.add(instance)
    return assets


def _probe_check(key, label, query, credentials):
    try:
        query()
        return {"key": key, "label": label, "success": True, "message": "查询权限验证通过"}
    except Exception as exc:
        diagnostic = cloud_probe_error(exc, credentials)
        if key == "disks" and diagnostic["category"] == "permission":
            diagnostic.update(message="云磁盘查询权限不足", suggestion="请授予当前账号 ecs:DescribeDisks 查询权限，并检查 RAM 策略限制。")
        return {"key": key, "label": label, "success": False, **diagnostic}


def probe_public_cloud(provider, regions, credentials):
    if provider not in {"aliyun", "tencent"} or not regions or len(regions) > 5:
        raise CloudCollectionError("请选择公有云平台及 1 至 5 个测试区域")
    results = []
    for region in regions:
        checks = []
        try:
            if provider == "aliyun":
                from alibabacloud_ecs20140526.client import Client
                from alibabacloud_ecs20140526.models import DescribeInstancesRequest, DescribeDisksRequest
                from alibabacloud_tea_openapi.models import Config

                client = Client(Config(
                    access_key_id=credentials["access_key_id"],
                    access_key_secret=credentials["access_key_secret"],
                    endpoint=f"ecs.{region}.aliyuncs.com",
                    connect_timeout=3000, read_timeout=3000,
                ))
                checks.append(_probe_check("instances", "ECS 主机查询", lambda: client.describe_instances(
                    DescribeInstancesRequest(region_id=region, page_size=1)), credentials))
                if checks[0]["success"]:
                    checks.append(_probe_check("disks", "ECS 磁盘查询", lambda: client.describe_disks(
                        DescribeDisksRequest(region_id=region, page_size=1)), credentials))
            else:
                from tencentcloud.common import credential
                from tencentcloud.common.profile.client_profile import ClientProfile
                from tencentcloud.common.profile.http_profile import HttpProfile
                from tencentcloud.cvm.v20170312 import cvm_client, models

                profile = ClientProfile()
                profile.httpProfile = HttpProfile(reqTimeout=3)
                client = cvm_client.CvmClient(credential.Credential(
                    credentials["access_key_id"], credentials["access_key_secret"]), region, profile)
                request = models.DescribeInstancesRequest()
                request.Limit = 1
                checks.append(_probe_check("instances", "CVM 主机及磁盘查询", lambda: client.DescribeInstances(request), credentials))
            failed = next((check for check in checks if not check["success"]), None)
            if failed:
                results.append({**failed, "region": region, "checks": checks})
            else:
                results.append({"region": region, "success": True, "message": "连接成功，具备资产查询权限", "checks": checks})
        except Exception as exc:
            results.append({"region": region, "success": False, **cloud_probe_error(exc, credentials)})
    return results


def _first(values):
    return values[0] if values else ""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise CloudCollectionError("云平台接口返回重定向，请核对接入地址")


def _request_json(url, *, method="GET", headers=None, payload=None, basic=None):
    """Bounded HTTPS request with system CA verification and no redirect following."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CloudCollectionError("云平台接口必须使用有效的 HTTPS 地址")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if basic:
        encoded = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
        request_headers["Authorization"] = f"Basic {encoded}"
    body = None if payload is None else json.dumps(payload).encode()
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with build_opener(HTTPSHandler(), _NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise CloudCollectionError("云平台接口响应过大")
            return (json.loads(raw) if raw else None), response.headers
    except HTTPError as exc:
        raise CloudCollectionError(f"云平台接口返回 HTTP {exc.code}，请检查只读权限与接入地址") from None
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise CloudCollectionError("云平台连接失败，请检查网络、TLS 证书和接口响应") from exc


def _addresses(values):
    """Prefer a usable private IPv4 address; never import loopback or link-local."""
    parsed = []
    for value in values:
        try:
            address = ipaddress.ip_address(str(value).split("/")[0])
        except ValueError:
            continue
        if address.version == 4 and not (address.is_loopback or address.is_link_local or address.is_unspecified):
            parsed.append(address)
    private = next((str(item) for item in parsed if item.is_private), "")
    return private or (str(parsed[0]) if parsed else "")


def _vmware(source, credentials):
    base = source.endpoint.rstrip("/")
    session_id, _ = _request_json(
        f"{base}/api/session", method="POST",
        basic=(credentials["access_key_id"], credentials["access_key_secret"]),
    )
    headers = {"vmware-api-session-id": session_id}
    try:
        vms, _ = _request_json(f"{base}/api/vcenter/vm", headers=headers)
        if len(vms) > MAX_ASSETS:
            raise CloudCollectionError("虚拟机超过单次预览上限 1000 台，请缩小账号可见范围")
        for vm in vms:
            vm_id = str(vm["vm"])
            try:
                interfaces, _ = _request_json(
                    f"{base}/api/vcenter/vm/{quote(vm_id, safe='')}/guest/networking/interfaces",
                    headers=headers,
                )
            except CloudCollectionError:
                interfaces = []
            addresses = [
                address.get("ip_address", "")
                for interface in interfaces
                for address in (interface.get("ip") or {}).get("ip_addresses", [])
            ]
            yield {
                "source_id": vm_id,
                "asset_type": "virtual_machine",
                "cloud_state": cloud_state(vm.get("power_state")),
                "hostname": vm.get("name") or vm_id,
                "internal_ip": _addresses(addresses),
                "os_family": "windows" if "WINDOWS" in str(vm.get("guest_OS", "")).upper() else "linux",
                "metadata": {"cloud_provider": "vmware", "power_state": vm.get("power_state", "")},
            }
    finally:
        try:
            _request_json(f"{base}/api/session", method="DELETE", headers=headers)
        except CloudCollectionError:
            pass


def _openstack(source, credentials, region):
    base = source.endpoint.rstrip("/")
    if not base.endswith("/v3"):
        base += "/v3"
    metadata = source.metadata or {}
    user_domain = metadata.get("user_domain_name") or "Default"
    project_domain = metadata.get("project_domain_name") or "Default"
    auth = {"auth": {
        "identity": {"methods": ["password"], "password": {"user": {
            "name": credentials["access_key_id"],
            "domain": {"name": user_domain},
            "password": credentials["access_key_secret"],
        }}},
        "scope": {"project": {"name": metadata["project_name"], "domain": {"name": project_domain}}},
    }}
    response, headers = _request_json(f"{base}/auth/tokens", method="POST", payload=auth)
    token = headers.get("X-Subject-Token")
    if not token:
        raise CloudCollectionError("OpenStack 未返回认证令牌")
    endpoints = [
        endpoint for service in response.get("token", {}).get("catalog", [])
        if service.get("type") == "compute"
        for endpoint in service.get("endpoints", [])
        if endpoint.get("interface") == "internal" and (endpoint.get("region") or endpoint.get("region_id")) == region
    ]
    if not endpoints:
        raise CloudCollectionError("OpenStack 服务目录中没有该区域的 internal Compute 端点")
    compute = endpoints[0]["url"].rstrip("/")
    marker = ""
    for _ in range(11):
        query = urlencode({"limit": PAGE_SIZE, **({"marker": marker} if marker else {})})
        page, _ = _request_json(f"{compute}/servers/detail?{query}", headers={"X-Auth-Token": token})
        servers = page.get("servers", [])
        for server in servers:
            ips = [
                entry.get("addr", "") for entries in server.get("addresses", {}).values()
                for entry in entries if entry.get("OS-EXT-IPS:type") != "floating"
            ]
            floating = [
                entry.get("addr", "") for entries in server.get("addresses", {}).values()
                for entry in entries if entry.get("OS-EXT-IPS:type") == "floating"
            ]
            yield {
                "source_id": server["id"],
                "asset_type": "virtual_machine",
                "cloud_state": cloud_state(server.get("status")),
                "hostname": server.get("name") or server["id"],
                "internal_ip": _addresses(ips),
                "external_ip": _addresses(floating),
                "metadata": {"cloud_provider": "openstack", "region": region, "status": server.get("status", "")},
            }
        if len(servers) < PAGE_SIZE:
            return
        next_marker = servers[-1]["id"]
        if next_marker == marker:
            raise CloudCollectionError("OpenStack 返回重复分页游标")
        marker = next_marker
    raise CloudCollectionError("OpenStack 资产分页超过上限")


def _pve(source, credentials):
    base = source.endpoint.rstrip("/")
    token_id = credentials["access_key_id"]
    headers = {"Authorization": f"PVEAPIToken={token_id}={credentials['access_key_secret']}"}
    response, _ = _request_json(f"{base}/api2/json/cluster/resources?type=vm", headers=headers)
    vms = response.get("data", [])
    if len(vms) > MAX_ASSETS:
        raise CloudCollectionError("PVE 虚拟机超过单次预览上限 1000 台，请缩小账号可见范围")
    for vm in vms:
        vm_type = vm.get("type")
        node = str(vm["node"])
        vmid = str(vm["vmid"])
        if vm_type == "qemu":
            try:
                guest, _ = _request_json(
                    f"{base}/api2/json/nodes/{quote(node, safe='')}/qemu/{quote(vmid, safe='')}/agent/network-get-interfaces",
                    headers=headers,
                )
            except CloudCollectionError:
                guest = {"data": {"result": []}}
            interfaces = guest.get("data", {}).get("result", [])
            addresses = [
                item.get("ip-address", "") for interface in interfaces
                for item in interface.get("ip-addresses", [])
            ]
        elif vm_type == "lxc":
            config, _ = _request_json(
                f"{base}/api2/json/nodes/{quote(node, safe='')}/lxc/{quote(vmid, safe='')}/config",
                headers=headers,
            )
            addresses = [
                part.removeprefix("ip=") for value in config.get("data", {}).values()
                if isinstance(value, str) for part in value.split(",") if part.startswith("ip=")
            ]
        else:
            continue
        yield {
            "source_id": f"{vm_type}:{vmid}",
            "asset_type": "virtual_machine",
            "cloud_state": cloud_state(vm.get("status")),
            "hostname": vm.get("name") or f"{vm_type}-{vmid}",
            "internal_ip": _addresses(addresses),
            "metadata": {"cloud_provider": "pve", "node": node, "vm_type": vm_type},
        }


def _instance_specs(cpu, memory, memory_scale=1):
    return {
        key: value * scale
        for key, value, scale in (("cpu_cores", cpu, 1), ("memory_mb", memory, memory_scale))
        if isinstance(value, int) and value > 0
    }


def _disk_specs(disks):
    return {
        "system_disk_gb": sum(disk["sizeGb"] for disk in disks if disk["type"] == "system"),
        "data_disk_gb": sum(disk["sizeGb"] for disk in disks if disk["type"] == "data"),
        "disk_summary": {"disks": disks},
    }


def _aliyun_disks(client, region, credentials):
    from alibabacloud_ecs20140526.models import DescribeDisksRequest

    by_instance = {}
    token = None
    seen = set()
    for _ in range(100):
        try:
            body = client.describe_disks(DescribeDisksRequest(
                region_id=region, max_results=PAGE_SIZE, next_token=token,
            )).body
        except Exception as exc:
            diagnostic = cloud_probe_error(exc, credentials)
            raise CloudCollectionError(
                f"{region} 磁盘查询 DescribeDisks 失败：{diagnostic['message']}；"
                f"错误码：{diagnostic['errorCode'] or '未返回'}。请确认 ecs:DescribeDisks 权限及网络。"
            ) from None
        for disk in (body.disks.disk if body.disks else []) or []:
            if disk.instance_id and disk.type in ("system", "data") and disk.size is not None:
                by_instance.setdefault(disk.instance_id, []).append({
                    "id": disk.disk_id, "type": disk.type, "sizeGb": disk.size,
                })
        token = body.next_token
        if not token:
            return by_instance
        if token in seen:
            raise CloudCollectionError("云磁盘接口返回重复分页游标")
        seen.add(token)
    raise CloudCollectionError("云磁盘分页超过上限，请缩小账号可见范围")


def _aliyun_region(region, credentials, instance_ids=None):
    from alibabacloud_ecs20140526.client import Client
    from alibabacloud_ecs20140526.models import DescribeInstancesRequest
    from alibabacloud_tea_openapi.models import Config

    client = Client(Config(
        access_key_id=credentials["access_key_id"],
        access_key_secret=credentials["access_key_secret"],
        endpoint=f"ecs.{region}.aliyuncs.com",
        connect_timeout=5000, read_timeout=15000,
    ))
    disks = _aliyun_disks(client, region, credentials)
    token = None
    seen = set()
    for _ in range(11):
        response = client.describe_instances(DescribeInstancesRequest(
            region_id=region, max_results=PAGE_SIZE, next_token=token,
            instance_ids=json.dumps(instance_ids) if instance_ids else None,
        ))
        body = response.body
        for item in (body.instances.instance if body.instances else []) or []:
            private = (item.vpc_attributes.private_ip_address.ip_address
                       if item.vpc_attributes and item.vpc_attributes.private_ip_address else [])
            if not private and item.inner_ip_address:
                private = item.inner_ip_address.ip_address
            public = item.public_ip_address.ip_address if item.public_ip_address else []
            eip = getattr(getattr(item, "eip_address", None), "ip_address", "")
            yield {
                "source_id": item.instance_id,
                "asset_type": "cloud_instance",
                "cloud_state": cloud_state(getattr(item, "status", None)),
                "region": region,
                **_instance_specs(getattr(item, "cpu", None), getattr(item, "memory", None)),
                **(_disk_specs(disks[item.instance_id]) if item.instance_id in disks else {}),
                "hostname": item.instance_name or item.host_name or item.instance_id,
                "internal_ip": _first(private),
                "external_ip": _first(public) or eip or "",
                "os_type": item.osname or "",
                "os_family": "windows" if (item.ostype or "").lower() == "windows" else "linux",
                "metadata": {"cloud_provider": "aliyun", "region": region, "zone": getattr(item, "zone_id", "") or "", "instance_type": item.instance_type},
            }
        token = body.next_token
        if not token:
            return
        if token in seen:
            raise CloudCollectionError("云接口返回重复分页游标")
        seen.add(token)
    raise CloudCollectionError("云资产分页超过上限")


def _tencent_region(region, credentials, instance_ids=None):
    from tencentcloud.common import credential
    from tencentcloud.cvm.v20170312 import cvm_client, models

    client = cvm_client.CvmClient(
        credential.Credential(credentials["access_key_id"], credentials["access_key_secret"]),
        region,
    )
    offset = 0
    for _ in range(11):
        request = models.DescribeInstancesRequest()
        if instance_ids:
            request.InstanceIds = instance_ids
        request.Offset = offset
        request.Limit = PAGE_SIZE
        response = client.DescribeInstances(request)
        instances = response.InstanceSet or []
        for item in instances:
            system_disk = getattr(item, "SystemDisk", None)
            data_disks = getattr(item, "DataDisks", None)
            disks = []
            if system_disk and system_disk.DiskSize is not None:
                disks.append({"id": system_disk.DiskId, "type": "system", "sizeGb": system_disk.DiskSize})
            for disk in data_disks or []:
                if disk.DiskSize is not None:
                    disks.append({"id": disk.DiskId, "type": "data", "sizeGb": disk.DiskSize})
            disk_fields = _disk_specs(disks)
            if system_disk is None or system_disk.DiskSize is None:
                disk_fields.pop("system_disk_gb")
            if data_disks is None or any(disk.DiskSize is None for disk in data_disks):
                disk_fields.pop("data_disk_gb")
            if "system_disk_gb" not in disk_fields or "data_disk_gb" not in disk_fields:
                disk_fields.pop("disk_summary")
            yield {
                "source_id": item.InstanceId,
                "asset_type": "cloud_instance",
                "cloud_state": cloud_state(getattr(item, "InstanceState", None)),
                "region": region,
                **_instance_specs(getattr(item, "CPU", None), getattr(item, "Memory", None), 1024),
                **disk_fields,
                "hostname": item.InstanceName or item.InstanceId,
                "internal_ip": _first(item.PrivateIpAddresses),
                "external_ip": _first(item.PublicIpAddresses),
                "os_type": item.OsName or "",
                "os_family": "windows" if "windows" in (item.OsName or "").lower() else "linux",
                "metadata": {"cloud_provider": "tencent", "region": region, "zone": getattr(getattr(item, "Placement", None), "Zone", "") or "", "instance_type": item.InstanceType},
            }
        offset += len(instances)
        if len(instances) < PAGE_SIZE or offset >= response.TotalCount:
            return
    raise CloudCollectionError("云资产分页超过上限")


def collect_cloud_assets(source):
    if source.source_type != AssetSource.SourceType.CLOUD or not source.is_active:
        raise CloudCollectionError("仅启用的云来源可拉取资产")
    if not source.credentials_encrypted:
        raise CloudCollectionError("云账号缺少凭据")
    credentials = json.loads(decrypt_secret(source.credentials_encrypted))
    public_providers = {
        AssetSource.CloudProvider.ALIYUN: _aliyun_region,
        AssetSource.CloudProvider.TENCENT: _tencent_region,
    }
    if source.cloud_provider == AssetSource.CloudProvider.VMWARE:
        return _validate_inventory(list(_vmware(source, credentials)))
    if source.cloud_provider == AssetSource.CloudProvider.PVE:
        return _validate_inventory(list(_pve(source, credentials)))
    if source.cloud_provider == AssetSource.CloudProvider.OPENSTACK:
        if not source.regions:
            raise CloudCollectionError("OpenStack 缺少同步区域")
        collector = lambda region: _openstack(source, credentials, region)
    elif source.cloud_provider in public_providers:
        if not source.regions:
            raise CloudCollectionError("公有云账号缺少同步区域")
        collector = lambda region: public_providers[source.cloud_provider](region, credentials)
    else:
        raise CloudCollectionError("不支持的云平台")
    assets = []
    for region in source.regions:
        try:
            for item in collector(region):
                assets.append(item)
                if len(assets) > MAX_ASSETS:
                    raise CloudCollectionError("云资产超过单次预览上限 1000 台，请缩小区域范围")
        except CloudCollectionError as exc:
            raise CloudCollectionError(f"区域 {region} 读取未完成：{exc}。本次未提交同步，不会删除或停用已有主机。") from None
        except Exception as exc:
            diagnostic = cloud_probe_error(exc, credentials)
            raise CloudCollectionError(
                f"区域 {region} 读取失败：{diagnostic['message']}；错误码：{diagnostic.get('errorCode') or '未返回'}。"
                "本次未提交同步，请检查该区域权限及网络。"
            ) from None
    return _validate_inventory(assets)
