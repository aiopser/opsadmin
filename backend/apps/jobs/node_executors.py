from .execution.snapshots import execution_node, execution_resource
from uuid import uuid4
from apps.jobs.events import append_run_event
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from django.utils import timezone
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from apps.automation.models import (
    ApiEndpoint,
    JenkinsServer,
    JenkinsBuild,
    JenkinsJob,
    NotificationChannel,
    NotificationRecord,
    NotificationTemplate,
)
from apps.cmdb.crypto import decrypt_secret
from apps.ops.executor import CONSOLE_OUTPUT_MAX_CHARS
from common.redaction import redact_text

from .execution.fencing import owned_node_queryset
from .models import JobEventLog, NodeRun

logger = logging.getLogger(__name__)


OUTPUT_PATTERN = re.compile(r"\[\[\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*::(.*?)\]\]")
JINJA_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


class NodeExecutionError(RuntimeError):
    pass


class NodeExecutionCanceled(NodeExecutionError):
    """Local waiting stopped; this does not assert an external operation stopped."""


def render_value(value, context):
    if isinstance(value, str):
        return JINJA_ENV.from_string(value).render(context)
    if isinstance(value, list):
        return [render_value(item, context) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, context) for key, item in value.items()}
    return value


def extract_output_vars(text):
    output = {}
    for key, raw_value in OUTPUT_PATTERN.findall(text or ""):
        value = raw_value.strip()
        try:
            output[key] = json.loads(value)
        except (TypeError, ValueError):
            output[key] = value
    return output


def _lookup_path(value, path):
    current = value
    for part in str(path or "").strip("$.").split("."):
        if not part:
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _matches_body_rule(response_json, rule):
    actual = _lookup_path(response_json, rule.get("path"))
    expected = rule.get("value")
    operator = rule.get("operator") or "eq"
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "contains":
        return str(expected) in str(actual)
    if operator == "exists":
        return actual is not None
    raise NodeExecutionError(f"Unsupported API success operator: {operator}")


def _validate_outbound_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise NodeExecutionError("Only HTTP and HTTPS URLs are supported")
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port)
        }
    except socket.gaierror as exc:
        raise NodeExecutionError(f"Unable to resolve host: {parsed.hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise NodeExecutionError(f"Blocked outbound address: {address}")
    return parsed


def _pairs_to_dict(items):
    if isinstance(items, dict):
        return dict(items)
    result = {}
    for item in items or []:
        if isinstance(item, dict) and item.get("enabled", True) and item.get("key"):
            result[str(item["key"])] = str(item.get("value") or "")
    return result


class ValidatedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = _validate_outbound_url(newurl)
        source = urlparse(req.full_url)

        def origin(parsed):
            return (
                parsed.scheme,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )

        if origin(source) != origin(target):
            raise NodeExecutionError("Cross-origin redirects are not allowed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _request(method, url, headers=None, body=None, timeout=30, verify_ssl=True):
    _validate_outbound_url(url)
    request = Request(url=url, data=body, headers=headers or {}, method=method)
    try:
        context = None if verify_ssl else ssl._create_unverified_context()
        opener = build_opener(ValidatedRedirectHandler(), HTTPSHandler(context=context))
        with opener.open(request, timeout=timeout) as response:
            return (
                response.status,
                dict(response.headers),
                response.read().decode("utf-8", errors="replace"),
            )
    except HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise NodeExecutionError(str(exc.reason)) from exc


def execute_api_endpoint(endpoint, context, console=None):
    """console：可选列表，收集请求行/状态行/响应体等控制台输出行（供节点落库展示）。"""
    lines = console if console is not None else []
    config = render_value(
        {
            "method": endpoint.method,
            "url": endpoint.url,
            "queryParams": endpoint.query_params,
            "headers": endpoint.headers,
            "body": endpoint.body,
        },
        context,
    )
    query = _pairs_to_dict(config["queryParams"])
    url = config["url"]
    if query:
        url = f"{url}{'&' if '?' in url else '?'}{urlencode(query)}"
    headers = _pairs_to_dict(config["headers"])
    cookies = _pairs_to_dict(endpoint.cookies)
    if cookies:
        headers["Cookie"] = "; ".join(
            f"{key}={value}" for key, value in cookies.items()
        )
    secret = decrypt_secret(endpoint.secret_encrypted)
    if endpoint.auth_type == ApiEndpoint.AuthType.BASIC:
        token = base64.b64encode(f"{endpoint.username}:{secret}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    elif endpoint.auth_type == ApiEndpoint.AuthType.BEARER:
        headers["Authorization"] = f"Bearer {secret}"
    elif endpoint.auth_type == ApiEndpoint.AuthType.API_KEY:
        if endpoint.api_key_location == "query":
            url = f"{url}{'&' if '?' in url else '?'}{urlencode({endpoint.api_key_name: secret})}"
        else:
            headers[endpoint.api_key_name] = secret

    body = None
    if endpoint.body_type == ApiEndpoint.BodyType.JSON:
        body = config["body"].encode()
        headers.setdefault("Content-Type", "application/json")
    elif endpoint.body_type == ApiEndpoint.BodyType.FORM:
        parsed_body = json.loads(config["body"] or "{}")
        body = urlencode(parsed_body).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif endpoint.body_type == ApiEndpoint.BodyType.RAW:
        body = config["body"].encode()

    lines.append(f"$ {config['method']} {url}")
    status, response_headers, response_text = _request(
        config["method"],
        url,
        headers,
        body,
        endpoint.timeout_seconds,
        endpoint.verify_ssl,
    )
    lines.append(f"HTTP {status}")
    if response_text:
        lines.append(response_text)
    rules = endpoint.success_rules or {}
    accepted = rules.get("statusCodes") or list(range(200, 400))
    if status not in accepted:
        raise NodeExecutionError(f"Unexpected HTTP status: {status}")
    try:
        response_json = json.loads(response_text)
    except ValueError:
        response_json = None
    body_rules = rules.get("bodyRules") or []
    if body_rules and response_json is None:
        raise NodeExecutionError("API success rules require a JSON response body")
    if any(not _matches_body_rule(response_json, rule) for rule in body_rules):
        raise NodeExecutionError("API response body did not match success rules")
    extracted = extract_output_vars(response_text)
    for extractor in endpoint.output_extractors or []:
        if not isinstance(extractor, dict) or not extractor.get("name"):
            continue
        value = (
            _lookup_path(response_json, extractor.get("path"))
            if response_json is not None
            else None
        )
        if value is None:
            if extractor.get("required"):
                raise NodeExecutionError(
                    f"Required API output was not found: {extractor.get('name')} ({extractor.get('path')})"
                )
            value = extractor.get("default")
        extracted[str(extractor["name"])] = value
    return {
        "status_code": status,
        "headers": response_headers,
        "body": response_json if response_json is not None else response_text,
        **extracted,
    }


def _persist_node_console(node_run, console, error=""):
    """通用节点没有 runner stdout，把控制台输出脱敏截断后落到 NodeRun；
    沿用 ansible 路径的归属 fencing（attempt/task/running），失效代次不会覆盖。"""
    lines = [*console]
    if error:
        lines.append(f"ERROR: {error}")
    text = redact_text("\n".join(lines))
    if len(text) > CONSOLE_OUTPUT_MAX_CHARS:
        text = text[:CONSOLE_OUTPUT_MAX_CHARS] + "\n...[output truncated]"
    try:
        owned_node_queryset(node_run).update(console_output=text)
    except Exception:
        logger.exception("Failed to persist console output for node %s", node_run.id)


def execute_api(node_run, context):
    endpoint = execution_resource(node_run)
    from .execution.settings_snapshot import effective_node_timeout

    endpoint.timeout_seconds = min(
        endpoint.timeout_seconds,
        effective_node_timeout(node_run.workflow_run, node_run.node_key),
    )
    console = []
    try:
        result = execute_api_endpoint(endpoint, context, console=console)
    except Exception as exc:
        _persist_node_console(
            node_run, console, error=str(exc) or exc.__class__.__name__
        )
        raise
    _persist_node_console(node_run, console)
    return result


def _jenkins_basic_auth(username, token):
    encoded = base64.b64encode(f"{username}:{token}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _jenkins_headers(server):
    return _jenkins_basic_auth(server.username, decrypt_secret(server.token_encrypted))


def _jenkins_job_endpoint(job_name):
    # job 名可能是中文等非 ASCII 字符，逐段 URL 编码，否则 http 客户端无法发送请求行
    name = str(job_name).strip("/")
    return "/".join(
        f"job/{quote(segment, safe='')}" for segment in name.split("/") if segment
    )


def fetch_jenkins_job_parameter_definitions(server, job_name):
    """查询任务定义的构建参数（name/type/default/choices）。

    网络异常抛 NodeExecutionError；探测地址不可用（非 200）返回 None，由调用方决定容忍策略。
    """
    probe_url = urljoin(
        server.base_url.rstrip("/") + "/",
        f"{_jenkins_job_endpoint(job_name)}/api/json?tree=property[parameterDefinitions[name,type,defaultParameterValue[value],choices]]",
    )
    status, _, body = _request(
        "GET",
        probe_url,
        _jenkins_headers(server),
        None,
        15,
        server.verify_ssl,
    )
    if status != 200:
        return None
    try:
        payload = json.loads(body or "{}")
    except ValueError as exc:
        raise NodeExecutionError("Jenkins 返回的参数定义不是合法 JSON") from exc
    definitions = []
    for prop in payload.get("property") or []:
        for definition in prop.get("parameterDefinitions") or []:
            if not definition.get("name"):
                continue
            default = definition.get("defaultParameterValue") or {}
            definitions.append(
                {
                    "name": definition["name"],
                    "type": definition.get("type") or "StringParameterDefinition",
                    "default": default.get("value"),
                    "choices": list(definition.get("choices") or []),
                }
            )
    return definitions


def _jenkins_job_parameter_names(server, job_name):
    """查询任务定义的构建参数名；查询失败返回 None（不阻塞触发）。"""
    definitions = fetch_jenkins_job_parameter_definitions(server, job_name)
    if definitions is None:
        return None
    return [definition["name"] for definition in definitions]


def trigger_jenkins_job(server, job_name, parameters=None, console=None):
    parameters = parameters or {}
    lines = console if console is not None else []
    endpoint = _jenkins_job_endpoint(job_name)
    lines.append(f"$ GET {job_name} 参数定义")
    defined = _jenkins_job_parameter_names(server, job_name)
    if defined:
        names = ", ".join(defined)
        lines.append(f"  定义了构建参数：{names}")
        if not parameters:
            raise NodeExecutionError(f"Jenkins 任务定义了构建参数（{names}），请在步骤参数中填写后再执行")
    if defined is not None and not defined and parameters:
        raise NodeExecutionError("Jenkins 任务未定义构建参数，请清空步骤中的参数配置")
    trigger_path = (
        f"{endpoint}/buildWithParameters" if parameters else f"{endpoint}/build"
    )
    trigger_url = urljoin(server.base_url.rstrip("/") + "/", trigger_path)
    if parameters:
        trigger_url = f"{trigger_url}?{urlencode(parameters)}"
        lines.append(f"$ POST {trigger_path}")
        for name, value in parameters.items():
            lines.append(f"  {name}={value}")
    else:
        lines.append(f"$ POST {trigger_path}")
    request_headers = _jenkins_headers(server)
    crumb_status, _, crumb_text = _request(
        "GET",
        urljoin(server.base_url.rstrip("/") + "/", "crumbIssuer/api/json"),
        request_headers,
        None,
        20,
        server.verify_ssl,
    )
    if crumb_status == 200:
        try:
            crumb = json.loads(crumb_text or "{}")
            if crumb.get("crumbRequestField") and crumb.get("crumb"):
                request_headers[crumb["crumbRequestField"]] = crumb["crumb"]
        except ValueError:
            pass
    # Jenkins 对 POST /build 强制要求表单 Content-Type，缺失时会返回 400 Nothing is submitted
    request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    status, headers, body = _request(
        "POST", trigger_url, request_headers, b"", 30, server.verify_ssl
    )
    lines.append(f"HTTP {status}")
    if status not in {200, 201, 202}:
        snippet = (body or "").strip()[:500]
        if snippet:
            lines.append(snippet)
        raise NodeExecutionError(f"Jenkins trigger failed: HTTP {status} {body}")
    queue_url = headers.get("Location") or headers.get("location")
    if not queue_url:
        raise NodeExecutionError("Jenkins did not return a queue location")
    return queue_url


def execute_jenkins(node_run, context):
    from apps.jobs.application.cancel import _is_workflow_run_canceled

    if _is_workflow_run_canceled(node_run.workflow_run):
        raise NodeExecutionCanceled("已停止等待 Jenkins；远端排队或构建可能继续运行")
    node = execution_node(node_run)
    job = execution_resource(node_run)
    server = job.server
    config = render_value(node.config or {}, context)
    # 流程设计器的「参数映射」写入节点 inputMapping；config.parameters 仅兼容旧快照
    mapping = render_value(node.input_mapping or {}, context)
    parameters = {**(config.get("parameters") or {}), **mapping}
    console: list[str] = []
    try:
        result = _run_jenkins_build(
            node_run, server, job, parameters, config, node, console
        )
    except Exception as exc:
        console.append(f"ERROR: {str(exc) or exc.__class__.__name__}")
        _persist_node_console(
            node_run, console, error=str(exc) or exc.__class__.__name__
        )
        raise
    _persist_node_console(node_run, console)
    return result


def _run_jenkins_build(node_run, server, job, parameters, config, node, console):
    from apps.jobs.application.cancel import _is_workflow_run_canceled

    job_name = job.name
    queue_url = trigger_jenkins_job(server, job_name, parameters, console=console)
    build_record = JenkinsBuild.objects.create(
        job=job,
        workflow_run=node_run.workflow_run,
        node_run=node_run,
        queue_url=queue_url,
        parameters=parameters,
    )

    def check_canceled():
        if _is_workflow_run_canceled(node_run.workflow_run):
            build_record.status = JenkinsBuild.Status.FAILED
            build_record.result = "WAIT_CANCELED"
            build_record.finished_at = timezone.now()
            build_record.save(
                update_fields=["status", "result", "finished_at", "updated_at"]
            )
            raise NodeExecutionCanceled("已停止等待 Jenkins；远端排队或构建可能继续运行")

    console.append(f"Queued Jenkins job {job_name}")

    from .execution.settings_snapshot import effective_node_timeout

    deadline = time.monotonic() + effective_node_timeout(
        node_run.workflow_run, node.node_key
    )
    build_url = ""
    while time.monotonic() < deadline:
        check_canceled()
        _, _, queue_text = _request(
            "GET",
            f"{queue_url.rstrip('/')}/api/json",
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        check_canceled()
        queue_data = json.loads(queue_text or "{}")
        build_url = (queue_data.get("executable") or {}).get("url") or ""
        if build_url:
            build_record.build_url = build_url
            build_record.build_number = (queue_data.get("executable") or {}).get(
                "number"
            )
            build_record.status = JenkinsBuild.Status.RUNNING
            build_record.started_at = timezone.now()
            build_record.save(
                update_fields=[
                    "build_url",
                    "build_number",
                    "status",
                    "started_at",
                    "updated_at",
                ]
            )
            break
        time.sleep(2)
    if not build_url:
        build_record.status = JenkinsBuild.Status.FAILED
        build_record.result = "QUEUE_TIMEOUT"
        build_record.finished_at = timezone.now()
        build_record.save(
            update_fields=["status", "result", "finished_at", "updated_at"]
        )
        raise NodeExecutionError("Timed out waiting for Jenkins build number")

    printed_size = 0
    while time.monotonic() < deadline:
        check_canceled()
        _, log_headers, log_text = _request(
            "GET",
            f"{build_url.rstrip('/')}/logText/progressiveText?start={printed_size}",
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        check_canceled()
        if log_text:
            console.extend(log_text.splitlines())
        printed_size = int(
            log_headers.get("X-Text-Size") or printed_size + len(log_text.encode())
        )
        status_code, _, build_text = _request(
            "GET",
            f"{build_url.rstrip('/')}/api/json",
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        check_canceled()
        if status_code != 200:
            build_record.status = JenkinsBuild.Status.FAILED
            build_record.result = f"HTTP_{status_code}"
            build_record.finished_at = timezone.now()
            build_record.save(
                update_fields=["status", "result", "finished_at", "updated_at"]
            )
            raise NodeExecutionError(
                f"Unable to query Jenkins build: HTTP {status_code}"
            )
        build_data = json.loads(build_text or "{}")
        if not build_data.get("building", False):
            result = build_data.get("result") or "UNKNOWN"
            build_record.console_output += log_text or ""
            build_record.result = result
            build_record.status = (
                JenkinsBuild.Status.SUCCESS
                if result == "SUCCESS"
                else JenkinsBuild.Status.ABORTED
                if result == "ABORTED"
                else JenkinsBuild.Status.FAILED
            )
            build_record.finished_at = timezone.now()
            build_record.save(
                update_fields=[
                    "console_output",
                    "result",
                    "status",
                    "finished_at",
                    "updated_at",
                ]
            )
            if result != "SUCCESS":
                raise NodeExecutionError(f"Jenkins build finished with {result}")
            return {
                "build_number": build_data.get("number"),
                "build_url": build_url,
                "result": result,
                "jenkins_build_id": build_record.id,
            }
        if log_text:
            build_record.console_output += log_text
            build_record.save(update_fields=["console_output", "updated_at"])
        time.sleep(2)
    build_record.status = JenkinsBuild.Status.FAILED
    build_record.result = "TIMEOUT"
    build_record.finished_at = timezone.now()
    build_record.save(update_fields=["status", "result", "finished_at", "updated_at"])
    raise NodeExecutionError("Jenkins build timed out")


def _parse_receivers(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except ValueError:
            pass
    return [item.strip() for item in text.split(",") if item.strip()]


def _sign_dingtalk_url(webhook, signing_secret):
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{signing_secret}"
    digest = hmac.new(
        signing_secret.encode(), string_to_sign.encode(), hashlib.sha256
    ).digest()
    sign = quote_plus(base64.b64encode(digest))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def _feishu_signature(signing_secret):
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{signing_secret}"
    digest = hmac.new(string_to_sign.encode(), b"", hashlib.sha256).digest()
    return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode()}


def send_notification(template, context, *, node_run=None, overrides=None, record=None):
    channel = template.channel
    if not template.is_active or not channel.is_active:
        raise NodeExecutionError("Notification template or channel is disabled")
    try:
        raw_config = {**(channel.config or {}), **(overrides or {})}
        payload_template = raw_config.pop("payload", None)
        config = render_value(raw_config, context)
        webhook = config.get("webhook") or decrypt_secret(channel.secret_encrypted)
        signing_secret = (
            decrypt_secret(channel.signing_secret_encrypted)
            if channel.signing_secret_encrypted
            else ""
        )
        subject = render_value(template.subject_template, context)
        message = render_value(template.body_template, context)
        receivers = _parse_receivers(
            config.get("receivers") or render_value(template.receiver_template, context)
        )
    except Exception as exc:
        if record is None:
            record = NotificationRecord.objects.create(
                template=template,
                channel=channel,
                workflow_run=node_run.workflow_run if node_run else None,
                node_run=node_run,
            )
        record.status = NotificationRecord.Status.FAILED
        record.failure_reason = f"通知模板渲染失败：{exc}"
        record.sent_at = timezone.now()
        record.save(update_fields=["status", "failure_reason", "sent_at", "updated_at"])
        raise
    if record is None:
        record = NotificationRecord.objects.create(
            template=template,
            channel=channel,
            workflow_run=node_run.workflow_run if node_run else None,
            node_run=node_run,
            subject=subject,
            body=message,
            receivers=receivers,
        )
    else:
        record.subject = subject
        record.body = message
        record.receivers = receivers
        record.save(update_fields=["subject", "body", "receivers", "updated_at"])
    try:
        if channel.channel_type == NotificationChannel.ChannelType.EMAIL:
            from django.conf import settings
            from django.core.mail import get_connection, send_mail
            from apps.automation.email_settings import get_email_delivery_config

            if not receivers:
                raise NodeExecutionError("Email notification requires receivers")
            delivery = get_email_delivery_config()
            if delivery:
                connection = get_connection(
                    backend="django.core.mail.backends.smtp.EmailBackend",
                    host=delivery["host"],
                    port=delivery["port"],
                    username=delivery["username"],
                    password=delivery["password"],
                    use_tls=delivery["useTls"],
                    use_ssl=delivery["useSsl"],
                )
                from_email = (
                    config.get("fromEmail")
                    or delivery["fromEmail"]
                    or getattr(settings, "DEFAULT_FROM_EMAIL", None)
                )
            else:
                if not getattr(settings, "EMAIL_HOST", ""):
                    raise NodeExecutionError(
                        "Email notification requires global SMTP configuration (EMAIL_HOST)"
                    )
                connection = None
                from_email = config.get("fromEmail") or getattr(
                    settings, "DEFAULT_FROM_EMAIL", None
                )
            sent = send_mail(
                (
                    f"{delivery['titlePrefix']}{subject}"
                    if delivery and delivery.get("titlePrefix")
                    else subject
                )
                or "DevOps workflow notification",
                message,
                from_email,
                receivers,
                connection=connection,
                fail_silently=False,
            )
            result = {"sent": sent, "receivers": receivers}
            response_status, response_text = 200, json.dumps(result, ensure_ascii=False)
        elif channel.channel_type in {
            NotificationChannel.ChannelType.WEBHOOK,
            NotificationChannel.ChannelType.WECOM,
            NotificationChannel.ChannelType.DINGTALK,
            NotificationChannel.ChannelType.FEISHU,
        }:
            if not webhook:
                raise NodeExecutionError("Notification channel URL is required")
            request_url = webhook
            if (
                signing_secret
                and channel.channel_type == NotificationChannel.ChannelType.DINGTALK
            ):
                request_url = _sign_dingtalk_url(webhook, signing_secret)
            if channel.channel_type == NotificationChannel.ChannelType.FEISHU:
                content = {"msg_type": "text", "content": {"text": message}}
                if signing_secret:
                    content.update(_feishu_signature(signing_secret))
            elif (
                channel.channel_type == NotificationChannel.ChannelType.WEBHOOK
                and payload_template is not None
            ):
                content = render_value(
                    payload_template,
                    {
                        **context,
                        "subject": subject,
                        "message": message,
                        "receivers": receivers,
                    },
                )
            else:
                content = {"msgtype": "text", "text": {"content": message}}
            payload = json.dumps(content, ensure_ascii=False).encode()
            from .execution.settings_snapshot import effective_node_timeout

            transport_timeout = (
                min(
                    15, effective_node_timeout(node_run.workflow_run, node_run.node_key)
                )
                if node_run is not None
                else 15
            )
            response_status, _, response_text = _request(
                "POST",
                request_url,
                {"Content-Type": "application/json"},
                payload,
                transport_timeout,
            )
            if response_status not in range(200, 300):
                raise NodeExecutionError(f"Notification failed: HTTP {response_status}")
            if channel.channel_type != NotificationChannel.ChannelType.WEBHOOK:
                try:
                    response_data = json.loads(response_text)
                except (TypeError, ValueError) as exc:
                    raise NodeExecutionError(
                        "Notification provider returned invalid JSON"
                    ) from exc
                if not isinstance(response_data, dict):
                    raise NodeExecutionError(
                        "Notification provider returned invalid response"
                    )
                if channel.channel_type == NotificationChannel.ChannelType.WECOM:
                    provider_code = response_data.get("errcode")
                else:
                    provider_code = response_data.get(
                        "code", response_data.get("errcode")
                    )
                if provider_code not in (0, "0"):
                    raise NodeExecutionError(
                        f"Notification provider rejected request: code {provider_code}"
                    )
            result = {"status_code": response_status}
        else:
            raise NodeExecutionError(
                f"Unsupported notification channel: {channel.channel_type}"
            )
        record.status = NotificationRecord.Status.SUCCESS
        record.failure_reason = ""
        record.next_retry_at = None
        record.response_status = response_status
        record.response_body = (
            response_text.replace(webhook, "[redacted]") if webhook else response_text
        )[:2048]
        record.sent_at = timezone.now()
        record.save(
            update_fields=[
                "status",
                "failure_reason",
                "next_retry_at",
                "response_status",
                "response_body",
                "sent_at",
                "updated_at",
            ]
        )
        return {**result, "notification_record_id": record.id}
    except Exception as exc:
        record.status = NotificationRecord.Status.FAILED
        reason = str(exc)
        record.failure_reason = (
            reason.replace(webhook, "[redacted]") if webhook else reason
        )
        record.sent_at = timezone.now()
        record.save(update_fields=["status", "failure_reason", "sent_at", "updated_at"])
        raise


def execute_notification(node_run, context):
    node = execution_node(node_run)
    template = execution_resource(node_run)
    run = node_run.workflow_run
    if run.workflow_version_id is None and node_run.node_key == "trial":
        from apps.automation.notification_preview import notification_context

        sample = (node.config or {}).get("notificationTestContext")
        context = sample if sample is not None else notification_context("failure")
    overrides = {
        key: value
        for key, value in (node.config or {}).items()
        if key != "notificationTestContext"
    }
    return send_notification(template, context, node_run=node_run, overrides=overrides)


EXECUTORS = {
    "api": execute_api,
    "jenkins": execute_jenkins,
    "notify": execute_notification,
}


def execute_generic_node(
    node_run_id, context, *, expected_attempt=None, expected_task_id=None
):
    node_run = NodeRun.objects.select_related("workflow_run", "workflow_node").get(
        id=node_run_id
    )
    if expected_attempt is not None and (
        node_run.attempt_count != expected_attempt
        or node_run.celery_task_id != expected_task_id
        or node_run.status != NodeRun.Status.RUNNING
    ):
        raise NodeExecutionCanceled("节点执行代次已失效，停止等待")
    node = execution_node(node_run)
    executor = EXECUTORS.get(node.node_type if node else "")
    if not executor:
        raise NodeExecutionError(
            f"Unsupported generic node type: {node.node_type if node else ''}"
        )
    deadline = node_run.workflow_run.workflow_deadline_at
    if deadline is not None and timezone.now() >= deadline:
        from billiard.exceptions import SoftTimeLimitExceeded

        raise SoftTimeLimitExceeded()

    return executor(node_run, context)


def record_generic_result(
    node_run,
    success,
    output_vars=None,
    error="",
    failure_status=NodeRun.Status.FAILED,
):
    from django.db import transaction
    from apps.jobs.execution.fencing import commit_node_result

    finished_at = timezone.now()
    started_at = node_run.started_at or finished_at
    with transaction.atomic():
        accepted = commit_node_result(
            node_run,
            {
                "status": NodeRun.Status.SUCCESS if success else failure_status,
                "output_vars": output_vars or {},
                "failure_reason": "" if success else error,
                "exit_code": 0 if success else 1,
                "finished_at": finished_at,
                "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            },
        )
        if not accepted:
            return False
        attempt_id = (
            node_run.attempts.filter(attempt=node_run.attempt_count)
            .values_list("id", flat=True)
            .first()
        )
        append_run_event(
            run_id=node_run.workflow_run_id,
            node_run_id=node_run.id,
            attempt_id=attempt_id,
            event_key=uuid4().hex,
            event={
                "event_type": "node_succeeded"
                if success
                else "node_canceled"
                if failure_status == NodeRun.Status.CANCELED
                else "node_failed",
                "message": f"Node {node_run.node_key} {('succeeded' if success else 'stopped')}.",
                "payload": {"node_key": node_run.node_key},
            },
        )
    return True
