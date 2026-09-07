from django.conf import settings
from django.db import models

from common.models import StandardModelMixin

__all__ = [
    "Role",
    "Permission",
    "CasbinRule",
    "PermissionAuditLog",
    "PermissionAccessLog",
    "OperationLog",
    "SystemConfig",
    "DictType",
    "DictItem",
    "Menu",
    "MenuButton",
]


class Role(StandardModelMixin):
    name = models.CharField(
        verbose_name="Name",
        help_text="Name",
        max_length=128,
        unique=True,
    )
    code = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Role code",
        help_text="角色编码，用于前端路由权限匹配（如 R_ADMIN）",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Role description",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    home_path = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name="Default home route",
        help_text="默认首页路由名（如 home）",
    )
    is_system = models.BooleanField(default=False, verbose_name="Built-in role")
    permission = models.ManyToManyField(
        to="Permission",
        verbose_name="Permission",
        blank=True,
        related_name="role",
    )

    def adapter(self):
        return [
            {
                "ptype": "g",
                "user": user.username,
                "role": self.name,
            }
            for user in self.user.all()
        ]

    def get_api_permissions(self):
        return self.permission.filter(
            type=Permission.PermissionType.API,
            is_active=True,
        )

    def get_menu_permissions(self):
        return self.permission.filter(
            type=Permission.PermissionType.MENU,
            is_active=True,
        )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "permission_role"
        unique_together = ("name",)
        verbose_name = verbose_name_plural = "Role"


class Permission(StandardModelMixin):
    class PermissionType(models.TextChoices):
        API = "api", "API"
        MENU = "menu", "Menu"
        BUTTON = "button", "Button"
        DATA = "data", "Data"

    name = models.CharField(verbose_name="Name", help_text="Name", max_length=64)
    code = models.CharField(max_length=128, unique=True, verbose_name="Permission code")
    type = models.CharField(
        max_length=16,
        choices=PermissionType.choices,
        default=PermissionType.API,
        verbose_name="Permission type",
    )
    path = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="API path"
    )
    method = models.CharField(
        max_length=128,
        verbose_name="HTTP method",
        blank=True,
        null=True,
    )
    pid = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="children",
        verbose_name="Parent permission",
    )
    is_system = models.BooleanField(default=False, verbose_name="Built-in permission")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    @property
    def is_api_permission(self):
        return self.type == self.PermissionType.API

    @property
    def is_menu_permission(self):
        return self.type == self.PermissionType.MENU

    @property
    def is_legacy_permission(self):
        return False

    def __str__(self):
        return self.code

    class Meta:
        db_table = "permission_permission"
        verbose_name = verbose_name_plural = "Permission"


class Menu(StandardModelMixin):
    class MenuType(models.TextChoices):
        CATALOG = "C", "Catalog"
        MENU = "M", "Menu"

    class IconType(models.TextChoices):
        ICONIFY = "1", "Iconify"
        LOCAL = "2", "Local svg icon"

    class MenuGroup(models.TextChoices):
        SYSTEM = "system", "System settings"

    order = models.IntegerField(verbose_name="Order")
    menu_type = models.CharField(
        max_length=1,
        choices=MenuType.choices,
        default=MenuType.MENU,
        db_index=True,
        verbose_name="Menu type",
    )
    path = models.CharField(verbose_name="Route path", max_length=64)
    component = models.CharField(
        verbose_name="View component",
        max_length=128,
        blank=True,
        null=True,
    )
    name = models.CharField(
        verbose_name="Route name", max_length=32, blank=True, null=True
    )
    title = models.CharField(verbose_name="Title", max_length=32, blank=True, null=True)
    icon = models.CharField(verbose_name="Icon", max_length=32, blank=True, null=True)
    icon_type = models.CharField(
        max_length=1,
        choices=IconType.choices,
        default=IconType.ICONIFY,
        verbose_name="Icon type",
        help_text="1=iconify 图标，2=本地 svg 图标",
    )
    i18n_key = models.CharField(
        verbose_name="I18n key",
        max_length=128,
        blank=True,
        null=True,
    )
    href = models.CharField(
        verbose_name="Outer link",
        max_length=128,
        blank=True,
        null=True,
    )
    multi_tab = models.BooleanField(default=False, verbose_name="Multi tab")
    fixed_index_in_tab = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Fixed index in tab",
    )
    query = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Route query",
        help_text='路由 query 参数，格式 [{"key": "id", "value": "1"}]',
    )
    constant = models.BooleanField(default=False, verbose_name="Constant route")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    show_icon = models.BooleanField(default=False, verbose_name="Show icon")
    redirect = models.CharField(
        verbose_name="Redirect",
        max_length=128,
        blank=True,
        null=True,
    )
    active_menu = models.CharField(
        verbose_name="Active menu",
        max_length=128,
        blank=True,
        null=True,
    )
    hidden = models.BooleanField(verbose_name="Hidden", default=False)
    always_show = models.BooleanField(verbose_name="Always show", default=True)
    no_cache = models.BooleanField(verbose_name="No cache", default=False)
    breadcrumb = models.BooleanField(verbose_name="Breadcrumb", default=False)
    affix = models.BooleanField(verbose_name="Affix", default=False)
    permission = models.ManyToManyField(
        to=Permission,
        verbose_name="Permission",
        blank=True,
    )
    menu_group = models.CharField(
        max_length=32,
        choices=MenuGroup.choices,
        default=MenuGroup.SYSTEM,
        db_index=True,
        verbose_name="Menu group",
    )
    pid = models.ForeignKey(
        "self",
        verbose_name="Parent menu",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.title or self.name or self.path or f"menu:{self.pk or 'new'}"

    def get_effective_permissions(self):
        return self.permission.filter(is_active=True)

    class Meta:
        db_table = "permission_menu"
        verbose_name_plural = verbose_name = "Menu"


class MenuButton(StandardModelMixin):
    """菜单按钮：独立于菜单树的按钮权限载体。

    按钮不再以 menu_type='B' 的 Menu 子节点表达，而是挂在所属菜单的
    ``buttons`` 反向关系上；按钮权限标识（Permission type='button'）与
    按钮触发的 API 权限通过 ``permission`` M2M 关联，供角色分配时展开。
    """

    menu = models.ForeignKey(
        Menu,
        verbose_name="Menu",
        on_delete=models.CASCADE,
        related_name="buttons",
    )
    code = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name="Button code",
    )
    desc = models.CharField(
        max_length=64,
        verbose_name="Button description",
    )
    permission = models.ManyToManyField(
        to=Permission,
        verbose_name="Permission",
        blank=True,
        related_name="menu_button",
    )

    def get_effective_permissions(self):
        return self.permission.filter(is_active=True)

    def __str__(self):
        return self.code

    class Meta:
        db_table = "permission_menu_button"
        unique_together = ("menu", "code")
        verbose_name_plural = verbose_name = "Menu button"


class DictType(StandardModelMixin):
    name = models.CharField(max_length=64, verbose_name="Dictionary name")
    dict_code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Dictionary code",
    )
    status = models.IntegerField(default=1, verbose_name="Status")
    remark = models.TextField(blank=True, default="", verbose_name="Remark")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "system_dict_type"
        verbose_name = verbose_name_plural = "Dictionary type"


class DictItem(StandardModelMixin):
    class TagType(models.TextChoices):
        NONE = "N", "None"
        PRIMARY = "P", "Primary"
        SUCCESS = "S", "Success"
        WARNING = "W", "Warning"
        INFO = "I", "Info"
        DANGER = "D", "Danger"

    dict_type = models.ForeignKey(
        DictType,
        related_name="items",
        on_delete=models.CASCADE,
        verbose_name="Dictionary type",
    )
    label = models.CharField(max_length=64, verbose_name="Label")
    value = models.CharField(max_length=128, verbose_name="Value")
    status = models.IntegerField(default=1, verbose_name="Status")
    sort = models.IntegerField(default=1, verbose_name="Sort")
    tag_type = models.CharField(
        max_length=1,
        choices=TagType.choices,
        default=TagType.NONE,
        verbose_name="Tag type",
    )

    def __str__(self):
        return f"{self.dict_type.dict_code}:{self.label}"

    class Meta:
        db_table = "system_dict_item"
        verbose_name = verbose_name_plural = "Dictionary item"
        unique_together = ("dict_type", "value")


class CasbinRule(StandardModelMixin):
    ptype = models.CharField(max_length=16, db_index=True, verbose_name="Policy type")
    v0 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v0")
    v1 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v1")
    v2 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v2")
    v3 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v3")
    v4 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v4")
    v5 = models.CharField(max_length=100, blank=True, null=True, verbose_name="v5")

    class Meta:
        db_table = "permission_casbin_rule"
        verbose_name = verbose_name_plural = "Casbin policy"
        unique_together = ("ptype", "v0", "v1", "v2", "v3", "v4", "v5")


class PermissionAuditLog(StandardModelMixin):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"
        RELATION_ADDED = "relation_added", "Relation added"
        RELATION_REMOVED = "relation_removed", "Relation removed"
        RELATION_CLEARED = "relation_cleared", "Relation cleared"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Actor",
    )
    actor_name = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Actor name"
    )
    action = models.CharField(
        max_length=32, choices=Action.choices, verbose_name="Action"
    )
    target_type = models.CharField(
        max_length=64, db_index=True, verbose_name="Target type"
    )
    target_id = models.CharField(
        max_length=64, blank=True, default="", verbose_name="Target ID"
    )
    target_repr = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Target"
    )
    changes = models.JSONField(default=dict, blank=True, verbose_name="Changes")

    class Meta:
        db_table = "permission_audit_log"
        verbose_name = verbose_name_plural = "Permission audit log"


class PermissionAccessLog(StandardModelMixin):
    class Status(models.TextChoices):
        DENIED = "denied", "Denied"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Actor",
    )
    actor_name = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Actor name"
    )
    path = models.CharField(max_length=255, db_index=True, verbose_name="Path")
    method = models.CharField(max_length=16, verbose_name="Method")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DENIED,
        verbose_name="Status",
    )
    reason = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Reason"
    )

    class Meta:
        db_table = "permission_access_log"
        verbose_name = verbose_name_plural = "Permission access log"


class OperationLog(StandardModelMixin):
    module = models.CharField(
        max_length=64, blank=True, default="", verbose_name="Module"
    )
    action_type = models.CharField(
        max_length=64, blank=True, default="", verbose_name="Action type"
    )
    title = models.CharField(
        max_length=255, blank=True, default="", verbose_name="Title"
    )
    content = models.TextField(blank=True, default="", verbose_name="Content")
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Operator",
    )
    operator_name = models.CharField(
        max_length=150, blank=True, default="", verbose_name="Operator name"
    )
    request_uri = models.CharField(
        max_length=255, db_index=True, verbose_name="Request URI"
    )
    request_method = models.CharField(max_length=16, verbose_name="Request method")
    ip = models.CharField(max_length=64, blank=True, default="", verbose_name="IP")
    region = models.CharField(
        max_length=128, blank=True, default="", verbose_name="Region"
    )
    device = models.CharField(
        max_length=128, blank=True, default="", verbose_name="Device"
    )
    browser = models.CharField(
        max_length=128, blank=True, default="", verbose_name="Browser"
    )
    os = models.CharField(max_length=128, blank=True, default="", verbose_name="OS")
    status = models.IntegerField(default=1, db_index=True, verbose_name="Status")
    execution_time = models.IntegerField(default=0, verbose_name="Execution time")
    error_msg = models.TextField(blank=True, default="", verbose_name="Error message")

    def __str__(self):
        return f"{self.request_method} {self.request_uri}"

    class Meta:
        db_table = "system_operation_log"
        verbose_name = verbose_name_plural = "Operation log"


class SystemConfig(StandardModelMixin):
    class ConfigGroup(models.TextChoices):
        BASIC = "basic", "Basic"
        SECURITY = "security", "Security"
        LOG = "log", "Log"
        FILE = "file", "File"

    config_name = models.CharField(max_length=64, verbose_name="Config name")
    config_key = models.CharField(
        max_length=128, unique=True, db_index=True, verbose_name="Config key"
    )
    config_value = models.TextField(blank=True, default="", verbose_name="Config value")
    config_group = models.CharField(
        max_length=32,
        choices=ConfigGroup.choices,
        default=ConfigGroup.BASIC,
        verbose_name="Config group",
    )
    remark = models.TextField(blank=True, default="", verbose_name="Remark")
    is_system = models.BooleanField(default=False, verbose_name="Built-in config")

    def __str__(self):
        return self.config_key

    class Meta:
        db_table = "system_config"
        verbose_name = verbose_name_plural = "System config"
