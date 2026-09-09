from .execution.snapshots import execution_node, execution_resource
from uuid import uuid4
from apps.jobs.events import append_run_event
import base64
import ipaddress
import json
import re
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
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

from .models import JobEventLog, NodeRun


OUTPUT_PATTERN = re.compile(r"\[\[\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*::(.*?)\]\]")
JINJA_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


class NodeExecutionError(RuntimeError):
    pass


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


def execute_api_endpoint(endpoint, context):
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

    status, response_headers, response_text = _request(
        config["method"],
        url,
        headers,
        body,
        endpoint.timeout_seconds,
        endpoint.verify_ssl,
    )
    print(f"{config['method']} {url}")
    print(f"HTTP {status}")
    if response_text:
        print(response_text)
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


def execute_api(node_run, context):
    endpoint = execution_resource(node_run)
    return execute_api_endpoint(endpoint, context)


def _jenkins_headers(server):
    token = decrypt_secret(server.token_encrypted)
    encoded = base64.b64encode(f"{server.username}:{token}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def trigger_jenkins_job(server, job_name, parameters=None):
    parameters = parameters or {}
    endpoint = f"job/{str(job_name).strip('/').replace('/', '/job/')}"
    trigger_path = (
        f"{endpoint}/buildWithParameters" if parameters else f"{endpoint}/build"
    )
    trigger_url = urljoin(server.base_url.rstrip("/") + "/", trigger_path)
    if parameters:
        trigger_url = f"{trigger_url}?{urlencode(parameters)}"
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
    status, headers, body = _request(
        "POST", trigger_url, request_headers, b"", 30, server.verify_ssl
    )
    if status not in {200, 201, 202}:
        raise NodeExecutionError(f"Jenkins trigger failed: HTTP {status} {body}")
    queue_url = headers.get("Location") or headers.get("location")
    if not queue_url:
        raise NodeExecutionError("Jenkins did not return a queue location")
    return queue_url


def execute_jenkins(node_run, context):
    node = execution_node(node_run)
    job = execution_resource(node_run)
    server = job.server
    config = render_value(node.config or {}, context)
    job_name = job.name
    parameters = config.get("parameters") or {}
    queue_url = trigger_jenkins_job(server, job_name, parameters)
    build_record = JenkinsBuild.objects.create(
        job=job,
        workflow_run=node_run.workflow_run,
        node_run=node_run,
        queue_url=queue_url,
        parameters=parameters,
    )
    print(f"Queued Jenkins job {job_name}")

    deadline = time.monotonic() + int(
        config.get("timeoutSeconds") or node.timeout_seconds
    )
    build_url = ""
    while time.monotonic() < deadline:
        _, _, queue_text = _request(
            "GET",
            f"{queue_url.rstrip('/')}/api/json",
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
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
        _, log_headers, log_text = _request(
            "GET",
            f"{build_url.rstrip('/')}/logText/progressiveText?start={printed_size}",
            _jenkins_headers(server),
            None,
            20,
            server.verify_ssl,
        )
        if log_text:
            print(log_text, end="" if log_text.endswith("\n") else "\n")
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


def send_notification(template, context, *, node_run=None, overrides=None):
    channel = template.channel
    config = render_value({**(channel.config or {}), **(overrides or {})}, context)
    webhook = config.get("webhook") or decrypt_secret(channel.secret_encrypted)
    subject = render_value(template.subject_template, context)
    message = render_value(template.body_template, context)
    receivers = _parse_receivers(
        config.get("receivers") or render_value(template.receiver_template, context)
    )
    record = NotificationRecord.objects.create(
        template=template,
        channel=channel,
        workflow_run=node_run.workflow_run if node_run else None,
        node_run=node_run,
        subject=subject,
        body=message,
        receivers=receivers,
    )
    try:
        if channel.channel_type == NotificationChannel.ChannelType.EMAIL:
            from django.conf import settings
            from django.core.mail import send_mail

            if not receivers:
                raise NodeExecutionError("Email notification requires receivers")
            sent = send_mail(
                subject or "DevOps workflow notification",
                message,
                config.get("fromEmail")
                or getattr(settings, "DEFAULT_FROM_EMAIL", None),
                receivers,
                fail_silently=False,
            )
            result = {"sent": sent, "receivers": receivers}
            response_status, response_text = 200, json.dumps(result, ensure_ascii=False)
        elif channel.channel_type in {
            NotificationChannel.ChannelType.WEBHOOK,
            NotificationChannel.ChannelType.WECOM,
            NotificationChannel.ChannelType.DINGTALK,
        }:
            payload = json.dumps(
                {"msgtype": "text", "text": {"content": message}}, ensure_ascii=False
            ).encode()
            response_status, _, response_text = _request(
                "POST", webhook, {"Content-Type": "application/json"}, payload, 15
            )
            if response_status not in range(200, 300):
                raise NodeExecutionError(
                    f"Notification failed: HTTP {response_status} {response_text}"
                )
            result = {"status_code": response_status, "response": response_text}
        else:
            raise NodeExecutionError(
                f"Unsupported notification channel: {channel.channel_type}"
            )
        record.status = NotificationRecord.Status.SUCCESS
        record.response_status = response_status
        record.response_body = response_text
        record.sent_at = timezone.now()
        record.save(
            update_fields=[
                "status",
                "response_status",
                "response_body",
                "sent_at",
                "updated_at",
            ]
        )
        print(message)
        return {**result, "notification_record_id": record.id}
    except Exception as exc:
        record.status = NotificationRecord.Status.FAILED
        record.failure_reason = str(exc)
        record.sent_at = timezone.now()
        record.save(update_fields=["status", "failure_reason", "sent_at", "updated_at"])
        raise


def execute_notification(node_run, context):
    node = execution_node(node_run)
    template = execution_resource(node_run)
    return send_notification(
        template, context, node_run=node_run, overrides=node.config or {}
    )


EXECUTORS = {
    "api": execute_api,
    "jenkins": execute_jenkins,
    "notify": execute_notification,
}


def execute_generic_node(node_run_id, context):
    node_run = NodeRun.objects.select_related("workflow_run", "workflow_node").get(
        id=node_run_id
    )
    node = execution_node(node_run)
    executor = EXECUTORS.get(node.node_type if node else "")
    if not executor:
        raise NodeExecutionError(
            f"Unsupported generic node type: {node.node_type if node else ''}"
        )
    return executor(node_run, context)


def record_generic_result(
    node_run,
    success,
    output_vars=None,
    error="",
    failure_status=NodeRun.Status.FAILED,
):
    finished_at = timezone.now()
    started_at = node_run.started_at or finished_at
    node_run.status = NodeRun.Status.SUCCESS if success else failure_status
    node_run.output_vars = output_vars or {}
    node_run.failure_reason = "" if success else error
    node_run.exit_code = 0 if success else 1
    node_run.finished_at = finished_at
    node_run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    node_run.save(
        update_fields=[
            "status",
            "output_vars",
            "failure_reason",
            "exit_code",
            "finished_at",
            "duration_ms",
            "updated_at",
        ]
    )
    append_run_event(
        run_id=(node_run.workflow_run).id,
        node_run_id=(node_run).id,
        event_key=uuid4().hex,
        event={
            "event_type": "node_succeeded" if success else "node_failed",
            "message": f"Node {node_run.node_key} {('succeeded' if success else 'failed')}.",
            "payload": {"node_key": node_run.node_key},
        },
    )
