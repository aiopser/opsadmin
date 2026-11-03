"""Private artifacts and a constrained Terraform subprocess adapter.

Provider bundles are installed and audited by the operator, never uploaded by applicants.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4
import tempfile
import signal
import time
from cryptography.fernet import InvalidToken

from django.conf import settings
from apps.cmdb.crypto import encrypt_secret, decrypt_secret
from .contracts import ProvisioningError


class ArtifactStore:
    def __init__(self, backup=False):
        configured = getattr(
            settings,
            "PROVISIONING_BACKUP_ROOT" if backup else "PROVISIONING_ARTIFACT_ROOT",
            "",
        )
        if not configured:
            raise ProvisioningError("尚未配置私有加密制品目录")
        self.root = Path(configured).resolve()
        for configured_public in [
            settings.MEDIA_ROOT,
            getattr(settings, "STATIC_ROOT", ""),
        ]:
            if configured_public:
                public = Path(configured_public).resolve()
                if self.root == public or public in self.root.parents:
                    raise ProvisioningError("制品目录不可位于公开 media/static 目录")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.working_root = self.root / "working"
        self.working_root.mkdir(exist_ok=True, mode=0o700)

    def put(self, value):
        key = uuid4().hex
        path = self.root / key
        from .state_crypto import StateKeyring

        if getattr(settings, "PROVISIONING_STATE_KEYS", {}):
            payload = json.dumps(StateKeyring().encrypt(value))
        else:
            # Compatibility for non-state legacy artifacts; state capture requires the keyring.
            payload = encrypt_secret(json.dumps(value))
        descriptor, name = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                os.chmod(name, 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
            if os.name == "posix":
                directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return key

    def get(self, key):
        if not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ProvisioningError("无效的制品标识")
        path = self.root / key
        if path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
            raise ProvisioningError("无效的制品文件")
        try:
            content = path.read_text(encoding="utf-8")
            if content.lstrip().startswith("{"):
                from .state_crypto import StateKeyring

                return StateKeyring().decrypt(json.loads(content))
            return json.loads(decrypt_secret(content))
        except (InvalidToken, UnicodeError, json.JSONDecodeError):
            raise ProvisioningError("制品解密或格式校验失败") from None


class TerraformRunner:
    def __init__(self, workspace, environment, on_tick=None):
        self.on_tick = on_tick
        self.workspace = Path(workspace)
        binary = Path(getattr(settings, "PROVISIONING_TERRAFORM_BINARY", ""))
        cli_config = Path(getattr(settings, "PROVISIONING_CLI_CONFIG", ""))
        self.version = getattr(settings, "PROVISIONING_TERRAFORM_VERSION", "")
        if (
            not binary.is_absolute()
            or not binary.is_file()
            or not cli_config.is_absolute()
            or not cli_config.is_file()
            or not self.version
        ):
            raise ProvisioningError("尚未配置固定版本 Terraform 和受控 Provider 镜像")
        self.binary = str(binary)
        # Do not inherit TF_CLI_ARGS, cloud credentials, or shell configuration.
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TMP",
                "TEMP",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            }
        }
        self.environment.update(environment)
        self.environment.update(
            TF_IN_AUTOMATION="1",
            TF_INPUT="0",
            TF_CLI_CONFIG_FILE=str(cli_config),
            CHECKPOINT_DISABLE="1",
        )
        version = json.loads(self.command(["version", "-json"]))
        if version.get("terraform_version") != self.version:
            raise ProvisioningError("Terraform 版本与部署锁定版本不一致")

    def command(self, arguments, timeout=300):
        if self.on_tick is not None:
            return self._managed_command(arguments, timeout)
        try:
            result = subprocess.run(
                [self.binary, *arguments],
                cwd=self.workspace,
                env=self.environment,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ProvisioningError("Terraform 执行超时，请核实资源结果后处理") from None
        if result.returncode:
            # Raw provider errors can contain secrets. Keep them out of business logs.
            raise ProvisioningError(
                f"Terraform {arguments[0]} 失败，退出码 {result.returncode}；请检查专用执行环境与云平台权限"
            )
        return result.stdout

    def _managed_command(self, arguments, timeout):
        if os.name != "posix":
            raise ProvisioningError("专用 Terraform 执行器仅支持 Linux；Windows 请使用隔离测试")
        if not self.on_tick():
            raise ProvisioningError("执行租约已失效，禁止启动执行进程")
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                [self.binary, *arguments],
                cwd=self.workspace,
                env=self.environment,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=errors,
                start_new_session=True,
            )
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if not self.on_tick():
                        raise ProvisioningError("执行租约已失效，结果待核实")
                    if time.monotonic() >= deadline:
                        raise ProvisioningError("Terraform 执行超时，结果待核实")
                    if (
                        os.fstat(output.fileno()).st_size
                        + os.fstat(errors.fileno()).st_size
                        > 32 * 1024 * 1024
                    ):
                        raise ProvisioningError("执行输出超过安全限制")
                    try:
                        code = process.wait(
                            timeout=min(15, max(0.1, deadline - time.monotonic()))
                        )
                        break
                    except subprocess.TimeoutExpired:
                        continue
                if code:
                    raise ProvisioningError(
                        f"Terraform {arguments[0]} 失败，退出码 {code}；请检查云平台权限及参数"
                    )
                if not self.on_tick():
                    raise ProvisioningError("执行租约已失效，结果待核实")
                if (
                    os.fstat(output.fileno()).st_size
                    + os.fstat(errors.fileno()).st_size
                    > 32 * 1024 * 1024
                ):
                    raise ProvisioningError("执行输出超过安全限制")
                output.seek(0)
                return output.read(32 * 1024 * 1024).decode("utf-8", errors="replace")
            finally:
                try:
                    # The parent may have exited while a provider child remains.
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if process.poll() is None:
                    process.wait()

    def initialize(self):
        self.command(["init", "-input=false", "-lockfile=readonly", "-no-color"])

    def plan(self):
        self.command(["plan", "-input=false", "-no-color", "-out=plan.bin"])
        return json.loads(self.command(["show", "-json", "plan.bin"]))

    def apply(self):
        return self.command(
            ["apply", "-input=false", "-no-color", "plan.bin"], timeout=1800
        )


def credential_environment(record):
    secret = json.loads(decrypt_secret(record.credential.encrypted_secret))
    if record.version.template.provider == "aliyun":
        return {
            "ALICLOUD_ACCESS_KEY": secret["access_key_id"],
            "ALICLOUD_SECRET_KEY": secret["access_key_secret"],
            "ALICLOUD_REGION": record.region,
        }
    return {
        "TENCENTCLOUD_SECRET_ID": secret["secret_id"],
        "TENCENTCLOUD_SECRET_KEY": secret["secret_key"],
        "TENCENTCLOUD_REGION": record.region,
    }


def prepare_bundle(record, workspace):
    root = Path(getattr(settings, "PROVISIONING_TEMPLATE_ROOT", "")).resolve()
    provider = record.version.template.provider
    bundle = root / provider
    required = ["main.tf.json", ".terraform.lock.hcl"]
    if not getattr(settings, "PROVISIONING_TEMPLATE_ROOT", "") or any(
        not (bundle / item).is_file() or (bundle / item).is_symlink()
        for item in required
    ):
        raise ProvisioningError("尚未安装经过审核并锁定 Provider 的资源模板包")
    manifest = record.version.constraints.get("bundle_digest")
    from .contracts import canonical_digest

    files = {name: (bundle / name).read_text(encoding="utf-8") for name in required}
    if not manifest or manifest != canonical_digest(files):
        raise ProvisioningError("资源模板包与已发布版本摘要不一致")
    for name, content in files.items():
        (workspace / name).write_text(content, encoding="utf-8")
    variables = {
        **record.parameters,
        "region": record.region,
        "request_id": str(record.pk),
    }
    variables["instance_count"] = variables.pop("count")
    (workspace / "terraform.tfvars.json").write_text(
        json.dumps(variables), encoding="utf-8"
    )


def archive_workspace(workspace):
    allowed = [
        "main.tf.json",
        ".terraform.lock.hcl",
        "terraform.tfvars.json",
        "plan.bin",
        "terraform.tfstate",
        "terraform.tfstate.backup",
    ]
    return {
        name: base64.b64encode((workspace / name).read_bytes()).decode()
        for name in allowed
        if (workspace / name).is_file() and not (workspace / name).is_symlink()
    }


def restore_workspace(files, workspace):
    allowed = {
        "main.tf.json",
        ".terraform.lock.hcl",
        "terraform.tfvars.json",
        "plan.bin",
        "terraform.tfstate",
        "terraform.tfstate.backup",
    }
    if not isinstance(files, dict) or set(files) - allowed:
        raise ProvisioningError("无效的执行制品")
    for name, encoded in files.items():
        (workspace / name).write_bytes(base64.b64decode(encoded, validate=True))
