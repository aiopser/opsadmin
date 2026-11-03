"""Bounded, redacted diagnostics for read-only public cloud probes."""

import re


def _redact(value, credentials, limit=800):
    text = str(value or "")
    for secret in credentials.values():
        if secret:
            text = text.replace(str(secret), "[已隐藏]")
    text = re.sub(r"https?://[^\s<>\"']+", "[链接已隐藏]", text, flags=re.I)
    text = re.sub(
        r"(?i)(authorization|accesskey(?:id|secret)?|secret(?:id|key)?|signature|securitytoken|token)"
        r"[\"']?\s*[:=]\s*[^\r\n,;]+", r"\1=[已隐藏]", text,
    )
    return text[:limit]


def _classify(error, code, status):
    text = f"{code} {type(error).__name__} {getattr(error, 'message', '')} {error}".lower()
    if isinstance(error, ImportError):
        return "dependency", "云 SDK 依赖缺失", "请在后端安装项目锁定的依赖，并重启服务。"
    if any(key in text for key in ("invalidregion", "regionid", "invalid.region", "region is", "region not")):
        return "region", "区域配置错误", "请核对平台与区域：阿里云如 cn-shanghai，腾讯云如 ap-shanghai。"
    if any(key in text for key in ("forbidden", "unauthorizedoperation", "accessdenied", "nopermission")):
        return "permission", "云主机查询权限不足", "请授予当前账号 ECS/CVM DescribeInstances 查询权限，并检查 RAM/CAM 策略限制。"
    if status == 401 or any(key in text for key in ("authfailure", "accesskey", "secretid", "signature", "invalidsecurity", "unauthorized")):
        return "authentication", "AccessKey 认证失败", "请确认 ID 与 Secret 成对有效，账号未禁用；签名过期时检查后端服务器时间。"
    if status == 403:
        return "permission", "云主机查询权限不足", "请检查当前账号的 ECS/CVM DescribeInstances 查询权限和 RAM/CAM 策略。"
    if any(key in text for key in ("timeout", "timed out")):
        return "timeout", "连接或响应超时", "请检查后端服务器到云 API 的出网、代理及防火墙，再重试。"
    if any(key in text for key in ("ssl", "certificate", "tls")):
        return "tls", "TLS 证书验证失败", "请检查后端系统 CA 证书、服务器时间及 HTTPS 代理证书。"
    if any(key in text for key in ("gaierror", "name resolution", "getaddrinfo", "nodename", "nameresolution")):
        return "dns", "云 API 域名解析失败", "请在后端服务器或容器中检查 DNS 解析和网络配置。"
    if any(key in text for key in ("connection", "network", "proxy", "unreachable")):
        return "network", "无法连接云 API", "请检查后端出网、防火墙及代理配置。"
    if status == 429 or any(key in text for key in ("throttl", "requestlimit")):
        return "rate_limit", "云接口请求被限流", "请稍后重试，并检查云账号 API 配额。"
    return "unknown", "云 API 调用失败", "请根据错误码和原因检查配置；联系云厂商时提供请求 ID。"


def cloud_probe_error(error, credentials):
    # Tea can wrap transport exceptions; keep the cloud response metadata while
    # using the underlying exception for network classification.
    data = getattr(error, "data", None)
    data = data if isinstance(data, dict) else {}
    code = getattr(error, "code", "") or data.get("Code", "")
    request_id = getattr(error, "requestId", "") or data.get("RequestId", "") or data.get("requestId", "")
    raw_status = getattr(error, "statusCode", None) or data.get("statusCode")
    status = int(raw_status) if str(raw_status).isdigit() else None
    cause = getattr(error, "inner_exception", None) or error.__cause__ or error
    category, message, suggestion = _classify(cause, code, status)
    detail = getattr(error, "message", "") or str(cause)
    return {
        "category": category, "message": message, "suggestion": suggestion,
        "errorCode": _redact(code, credentials, 160),
        "requestId": _redact(request_id, credentials, 160),
        "httpStatus": status, "detail": _redact(detail, credentials),
    }
