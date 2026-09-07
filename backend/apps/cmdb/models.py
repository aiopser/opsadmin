from django.db import models

from common.models import StandardModelMixin


class Business(StandardModelMixin):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_business"
        ordering = ["code"]


class ServiceTreeNode(StandardModelMixin):
    class NodeType(models.TextChoices):
        ENVIRONMENT = "environment", "Environment"
        REGION = "region", "Region"
        MODULE = "module", "Module"

    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="service_tree_nodes",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    node_type = models.CharField(max_length=32, choices=NodeType.choices)
    description = models.TextField(blank=True, default="")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_service_tree_node"
        ordering = ["sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=("business", "code"),
                name="cmdb_service_tree_business_code_uniq",
            )
        ]


class AssetSource(StandardModelMixin):
    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        CLOUD = "cloud", "Cloud"
        EXTERNAL_CMDB = "external_cmdb", "External CMDB"

    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    endpoint = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_asset_source"
        ordering = ["code"]


class AssetSyncRecord(StandardModelMixin):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    source = models.ForeignKey(
        AssetSource,
        on_delete=models.PROTECT,
        related_name="sync_records",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    task_id = models.CharField(max_length=128, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "cmdb_asset_sync_record"
        ordering = ["-created_at", "-id"]


class WorkerPool(StandardModelMixin):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    queue_name = models.CharField(max_length=128)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    concurrency_limit = models.IntegerField(default=5)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_worker_pool"
        ordering = ["code"]


class CredentialRef(StandardModelMixin):
    class CredentialType(models.TextChoices):
        SSH_KEY = "ssh_key", "SSH Key"
        PASSWORD = "password", "Password"
        VAULT_REF = "vault_ref", "Vault Reference"

    class Scope(models.TextChoices):
        GLOBAL = "global", "Global"
        ENVIRONMENT = "environment", "Environment"
        HOST_GROUP = "host_group", "Host Group"
        HOST = "host", "Host"

    class ConnectionProtocol(models.TextChoices):
        SSH = "ssh", "SSH"
        WINRM = "winrm", "WinRM"
        LOCAL = "local", "Local"

    name = models.CharField(max_length=128)
    type = models.CharField(max_length=32, choices=CredentialType.choices)
    scope = models.CharField(max_length=32, choices=Scope.choices)
    connection_type = models.CharField(
        max_length=16,
        choices=ConnectionProtocol.choices,
        default=ConnectionProtocol.SSH,
    )
    username = models.CharField(max_length=64, blank=True, default="root")
    default_port = models.IntegerField(null=True, blank=True)
    secret_ref = models.CharField(max_length=255, blank=True, default="")
    encrypted_secret = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    @property
    def effective_port(self):
        """Return default_port or infer from connection_type."""
        if self.default_port:
            return self.default_port
        return {"ssh": 22, "winrm": 5985, "local": None}.get(self.connection_type)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_credential_ref"
        ordering = ["name"]


class AssetHost(StandardModelMixin):
    class AssetType(models.TextChoices):
        SERVER = "server", "Server"
        VIRTUAL_MACHINE = "virtual_machine", "Virtual Machine"
        CLOUD_INSTANCE = "cloud_instance", "Cloud Instance"

    class OSFamily(models.TextChoices):
        LINUX = "linux", "Linux"
        WINDOWS = "windows", "Windows"

    class HostStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        RETIRED = "retired", "Retired"

    class ConnectionType(models.TextChoices):
        SSH = "ssh", "SSH"
        WINRM = "winrm", "WinRM"
        LOCAL = "local", "Local"

    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        CLOUD = "cloud", "Cloud"
        EXTERNAL_CMDB = "external_cmdb", "External CMDB"

    hostname = models.CharField(max_length=128, db_index=True)
    primary_ip = models.GenericIPAddressField(db_index=True)
    asset_type = models.CharField(
        max_length=32,
        choices=AssetType.choices,
        default=AssetType.SERVER,
    )
    os_family = models.CharField(max_length=16, choices=OSFamily.choices)
    os_type = models.CharField(max_length=64, blank=True, default="")
    image_name = models.CharField(max_length=128, blank=True, default="")
    cpu_cores = models.IntegerField(default=0)
    memory_mb = models.IntegerField(default=0)
    system_disk_gb = models.IntegerField(default=0)
    data_disk_gb = models.IntegerField(default=0)
    disk_summary = models.JSONField(default=dict, blank=True)
    environment = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=HostStatus.choices,
        default=HostStatus.ACTIVE,
    )
    service_node = models.ForeignKey(
        ServiceTreeNode,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosts",
    )
    asset_source = models.ForeignKey(
        AssetSource,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosts",
    )
    owner_team = models.CharField(max_length=128, blank=True, default="")
    app_code = models.CharField(max_length=128, blank=True, default="")
    connection_type = models.CharField(max_length=16, choices=ConnectionType.choices)
    connection_port = models.IntegerField(default=22)
    credential_ref = models.ForeignKey(
        CredentialRef,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    default_gateway = models.ForeignKey(
        "jobs.Gateway",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosts",
    )
    ansible_connection_vars = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
    )
    source_id = models.CharField(max_length=128, blank=True, default="")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_discovered_at = models.DateTimeField(null=True, blank=True)

    def config_summary(self):
        memory_gb = int(self.memory_mb / 1024) if self.memory_mb else 0
        return (
            f"{self.cpu_cores}C / {memory_gb}G / "
            f"{self.system_disk_gb}G / {self.data_disk_gb}G"
        )

    def __str__(self):
        return self.hostname

    class Meta:
        db_table = "cmdb_asset_host"
        ordering = ["hostname", "id"]
        unique_together = ("primary_ip", "hostname")


class HostGroup(StandardModelMixin):
    class GroupType(models.TextChoices):
        STATIC = "static", "Static"
        DYNAMIC = "dynamic", "Dynamic"

    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    description = models.TextField(blank=True, default="")
    group_type = models.CharField(
        max_length=16,
        choices=GroupType.choices,
        default=GroupType.STATIC,
    )
    match_rule = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cmdb_host_group"
        ordering = ["name", "id"]


class HostGroupMembership(StandardModelMixin):
    host = models.ForeignKey(
        AssetHost,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    group = models.ForeignKey(
        HostGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    class Meta:
        db_table = "cmdb_host_group_membership"
        unique_together = ("host", "group")


class HostTag(StandardModelMixin):
    key = models.CharField(max_length=64)
    value = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.key}:{self.value}"

    class Meta:
        db_table = "cmdb_host_tag"
        unique_together = ("key", "value")
        ordering = ["key", "value"]


class HostTagBinding(StandardModelMixin):
    host = models.ForeignKey(
        AssetHost,
        on_delete=models.CASCADE,
        related_name="tag_bindings",
    )
    tag = models.ForeignKey(
        HostTag,
        on_delete=models.CASCADE,
        related_name="bindings",
    )

    class Meta:
        db_table = "cmdb_host_tag_binding"
        unique_together = ("host", "tag")
