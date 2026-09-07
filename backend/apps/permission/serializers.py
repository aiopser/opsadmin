from common.api.serializers import StandardModelSerializer
from rest_framework import serializers

from .models import DictItem, DictType, Role, Menu, MenuButton, Permission, SystemConfig
from .services import infer_system_setting_category


class RoleSerializer(StandardModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"

    @staticmethod
    def _to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value == 1
        if value is None:
            return True
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def to_internal_value(self, data):
        mutable = data.copy()
        # soybean 前端 camelCase 字段映射
        if "roleName" in mutable and "name" not in mutable:
            mutable["name"] = mutable.get("roleName")
        if "roleCode" in mutable and "code" not in mutable:
            mutable["code"] = mutable.get("roleCode")
        if "roleDesc" in mutable and "description" not in mutable:
            mutable["description"] = mutable.get("roleDesc") or ""
        if "homePath" in mutable and "home_path" not in mutable:
            mutable["home_path"] = mutable.get("homePath") or None
        if "status" in mutable:
            # '1' 启用 / '2' 禁用（或 1/0、true/false）
            mutable["is_active"] = self._to_bool(mutable.get("status"))
            mutable.pop("status", None)
        # 兼容旧模板前端：仅传 code 时作为 name 使用
        if "code" in mutable and "name" not in mutable:
            mutable["name"] = mutable.get("code")
        if "permissionIds" in mutable and "permission" not in mutable:
            mutable["permission"] = mutable.get("permissionIds")
        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        representation = super(RoleSerializer, self).to_representation(instance)
        representation["permission_codes"] = [
            permission.code for permission in instance.permission.all()
        ]
        representation["api_permission_codes"] = [
            permission.code for permission in instance.get_api_permissions()
        ]
        representation["menu_permission_codes"] = [
            permission.code for permission in instance.get_menu_permissions()
        ]
        # code 为空时回退 name，保证旧消费方语义不变
        representation["code"] = instance.code or instance.name
        representation["roleName"] = instance.name
        representation["roleCode"] = instance.code or instance.name
        representation["roleDesc"] = instance.description
        representation["status"] = "1" if instance.is_active else "2"
        representation["homePath"] = instance.home_path
        representation["sort"] = instance.id
        representation["dataScope"] = 1
        representation["dataScopeLabel"] = "All data"
        representation["updateTime"] = instance.updated_at
        return representation


class PermissionSerializer(StandardModelSerializer):
    class Meta:
        model = Permission
        fields = "__all__"

    def to_representation(self, instance):
        representation = super(PermissionSerializer, self).to_representation(instance)
        representation["role_names"] = [role.name for role in instance.role.all()]
        representation["is_api_permission"] = instance.is_api_permission
        representation["is_menu_permission"] = instance.is_menu_permission
        representation["is_legacy_permission"] = instance.is_legacy_permission
        return representation


class MenuSerializer(StandardModelSerializer):
    class Meta:
        model = Menu
        fields = "__all__"

    @staticmethod
    def _normalize_parent_id(value):
        if value in (None, "", "0", 0):
            return None
        return value

    @staticmethod
    def _to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        if value is None:
            return False
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _normalize_route_path(path, parent_id):
        if not path:
            return path
        path = str(path).strip()
        if path.startswith(("http://", "https://")):
            return path
        if parent_id in (None, "", "0", 0) and not path.startswith("/"):
            return f"/{path}"
        return path

    @staticmethod
    def _route_code(path):
        raw = (path or "").strip().strip("/")
        return raw.replace("/", ":").replace("-", "_") or "root"

    def _get_menu_type(self, mutable):
        menu_type = mutable.get("type") or mutable.get("menu_type")
        if menu_type is None and self.instance is not None:
            menu_type = self.instance.menu_type
        return menu_type or Menu.MenuType.MENU

    def _normalize_component(self, component, menu_type, parent_id):
        if menu_type == Menu.MenuType.CATALOG:
            return "Layout" if parent_id in (None, "", "0", 0) else "ParentView"
        return component

    def to_internal_value(self, data):
        mutable = data.copy()
        if "parentId" in mutable:
            mutable["pid"] = self._normalize_parent_id(mutable.get("parentId"))
        elif "pid" in mutable:
            mutable["pid"] = self._normalize_parent_id(mutable.get("pid"))
        if "sort" in mutable:
            mutable["order"] = mutable.get("sort")
        if "type" in mutable:
            mutable["menu_type"] = mutable.get("type")
        menu_type = self._get_menu_type(mutable)
        if "routeName" in mutable:
            mutable["name"] = mutable.get("routeName")
        if "routePath" in mutable:
            mutable["path"] = mutable.get("routePath")
        if "path" in mutable:
            parent_id = mutable.get("pid")
            if (
                parent_id is None
                and self.instance is not None
                and "parentId" not in mutable
                and "pid" not in mutable
            ):
                parent_id = self.instance.pid_id
            mutable["path"] = self._normalize_route_path(mutable.get("path"), parent_id)
        if menu_type == Menu.MenuType.CATALOG and not mutable.get("name"):
            mutable["name"] = mutable.get("path")
        if "component" in mutable or "type" in mutable:
            mutable["component"] = self._normalize_component(
                mutable.get("component"),
                menu_type,
                mutable.get("pid"),
            )
        if "visible" in mutable:
            mutable["hidden"] = not self._to_bool(mutable.get("visible"))
        if "hideInMenu" in mutable:
            mutable["hidden"] = self._to_bool(mutable.get("hideInMenu"))
        if "i18nKey" in mutable:
            mutable["i18n_key"] = mutable.get("i18nKey") or None
        if "iconType" in mutable:
            mutable["icon_type"] = mutable.get("iconType")
        if "multiTab" in mutable:
            mutable["multi_tab"] = self._to_bool(mutable.get("multiTab"))
        if "fixedIndexInTab" in mutable:
            raw_fixed = mutable.get("fixedIndexInTab")
            mutable["fixed_index_in_tab"] = (
                int(raw_fixed) if raw_fixed is not None and str(raw_fixed).strip() != "" else None
            )
        if "status" in mutable:
            # '1' 启用 / '2' 禁用
            mutable["is_active"] = self._to_bool(mutable.get("status"))
            mutable.pop("status", None)
        if "keepAlive" in mutable:
            mutable["no_cache"] = not self._to_bool(mutable.get("keepAlive"))
        if "alwaysShow" in mutable:
            mutable["always_show"] = self._to_bool(mutable.get("alwaysShow"))
        if "showIcon" in mutable:
            mutable["show_icon"] = self._to_bool(mutable.get("showIcon"))
        if "icon" in mutable and not str(mutable.get("icon") or "").strip():
            # Clearing the icon in the menu editor must also disable icon
            # rendering; otherwise validation rejects the otherwise valid edit
            # because the existing show_icon flag is still true.
            mutable["show_icon"] = False
        if menu_type == Menu.MenuType.CATALOG and self.instance is None:
            mutable["always_show"] = True
        mutable.pop("perm", None)
        mutable.pop("buttons", None)
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        menu_type = attrs.get("menu_type") or getattr(self.instance, "menu_type", None)
        path = attrs.get("path", getattr(self.instance, "path", None))
        component = attrs.get("component", getattr(self.instance, "component", None))
        route_name = attrs.get("name", getattr(self.instance, "name", None))
        if menu_type == Menu.MenuType.CATALOG and not path:
            raise serializers.ValidationError({"routePath": "目录类型必须设置路由路径"})
        if menu_type == Menu.MenuType.MENU:
            if not path:
                raise serializers.ValidationError({"routePath": "菜单类型必须设置路由路径"})
            if not component:
                raise serializers.ValidationError({"component": "菜单类型必须设置组件路径"})
            if not route_name:
                raise serializers.ValidationError({"routeName": "菜单类型必须设置路由名称"})
        show_icon = attrs.get("show_icon", getattr(self.instance, "show_icon", False))
        icon = attrs.get("icon", getattr(self.instance, "icon", ""))
        if show_icon and not (icon or "").strip():
            raise serializers.ValidationError({"icon": "启用图标显示时必须选择图标"})
        return attrs

    def _get_perm_code(self):
        if not hasattr(self, "initial_data"):
            return None
        return (self.initial_data or {}).get("perm")

    def _get_api_permission_ids(self):
        if not hasattr(self, "initial_data"):
            return None
        initial = self.initial_data or {}
        if "apiPermissionIds" not in initial and "api_permission_ids" not in initial:
            return None
        values = (
            initial.get("apiPermissionIds") or initial.get("api_permission_ids") or []
        )
        if isinstance(values, str):
            values = [item for item in values.split(",") if item]
        return values

    def _sync_permission(self, instance):
        perm_code = self._get_perm_code()
        existing = instance.permission.filter(
            type=Permission.PermissionType.MENU
        ).first()
        code = perm_code or (
            existing.code if existing else f"menu:{self._route_code(instance.path)}"
        )
        if not code:
            return
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "name": instance.title or instance.name or code,
                "type": Permission.PermissionType.MENU,
                "path": instance.path,
                "method": "GET",
                "is_system": existing.is_system if existing and not perm_code else False,
                "is_active": True,
            },
        )
        api_permission_ids = self._get_api_permission_ids()
        if api_permission_ids is None:
            api_permissions = instance.permission.filter(
                type=Permission.PermissionType.API,
                is_active=True,
            )
        else:
            api_permissions = Permission.objects.filter(
                id__in=api_permission_ids,
                type=Permission.PermissionType.API,
                is_active=True,
            )
        instance.permission.set([permission, *api_permissions])

    def _get_buttons_payload(self):
        if not hasattr(self, "initial_data"):
            return None
        initial = self.initial_data or {}
        if "buttons" not in initial:
            return None
        return initial.get("buttons") or []

    @staticmethod
    def _normalize_buttons_payload(buttons):
        normalized = []
        seen_codes = set()
        for item in buttons:
            if isinstance(item, dict):
                code = str(item.get("code") or "").strip()
                desc = str(
                    item.get("desc") or item.get("title") or item.get("name") or ""
                ).strip()
                api_permission_ids = item.get("apiPermissionIds")
            else:
                code = str(item or "").strip()
                desc = ""
                api_permission_ids = None
            if not code or code in seen_codes:
                continue
            if isinstance(api_permission_ids, str):
                api_permission_ids = [
                    value for value in api_permission_ids.split(",") if value
                ]
            seen_codes.add(code)
            normalized.append(
                {
                    "code": code[:128],
                    "desc": desc[:64],
                    "apiPermissionIds": api_permission_ids,
                }
            )
        return normalized

    def _sync_buttons(self, instance):
        """按提交的 buttons 数组全量同步菜单按钮及其权限绑定。"""
        buttons_payload = self._get_buttons_payload()
        if buttons_payload is None:
            return
        buttons = self._normalize_buttons_payload(buttons_payload)
        existing = {button.code: button for button in instance.buttons.all()}
        for item in buttons:
            code = item["code"]
            button = existing.get(code)
            if button is None:
                button = MenuButton.objects.create(
                    menu=instance,
                    code=code,
                    desc=item["desc"],
                )
            elif button.desc != item["desc"]:
                button.desc = item["desc"]
                button.save(update_fields=["desc"])
            permission = Permission.objects.filter(code=code).first()
            if permission is None:
                permission = Permission.objects.create(
                    name=item["desc"] or code,
                    code=code,
                    type=Permission.PermissionType.BUTTON,
                    is_active=True,
                )
            elif permission.type != Permission.PermissionType.BUTTON:
                permission.type = Permission.PermissionType.BUTTON
                permission.path = None
                permission.method = None
                permission.save(update_fields=["type", "path", "method"])
            api_permission_ids = item["apiPermissionIds"]
            if api_permission_ids is None:
                api_permissions = list(
                    button.permission.filter(
                        type=Permission.PermissionType.API,
                        is_active=True,
                    )
                )
            else:
                api_permissions = list(
                    Permission.objects.filter(
                        id__in=api_permission_ids,
                        type=Permission.PermissionType.API,
                        is_active=True,
                    )
                )
            button.permission.set([permission, *api_permissions])
        for code, button in existing.items():
            if code not in {item["code"] for item in buttons}:
                button.delete()

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._sync_permission(instance)
        self._sync_buttons(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._sync_permission(instance)
        self._sync_buttons(instance)
        return instance

    def to_representation(self, instance):
        representation = super(MenuSerializer, self).to_representation(instance)
        # 使用 prefetch 缓存，避免 N+1 查询
        all_perms = list(instance.permission.all())
        representation["roles"] = sorted(
            {role.name for permission in all_perms for role in permission.role.all()}
        )
        representation["permission_codes"] = sorted(
            permission.code for permission in all_perms
        )
        representation["effective_permission_codes"] = sorted(
            permission.code for permission in all_perms if permission.is_active
        )
        representation["system_category"] = (
            infer_system_setting_category(instance)
            if instance.menu_group == Menu.MenuGroup.SYSTEM
            else None
        )
        representation["parentId"] = str(instance.pid_id) if instance.pid_id else "0"
        representation["sort"] = instance.order
        representation["visible"] = 0 if instance.hidden else 1
        representation["type"] = instance.menu_type
        base_permission = next(
            (
                permission
                for permission in all_perms
                if permission.type == Permission.PermissionType.MENU
            ),
            None,
        )
        api_permissions = [
            permission
            for permission in all_perms
            if permission.type == Permission.PermissionType.API and permission.is_active
        ]
        representation["perm"] = base_permission.code if base_permission else None
        representation["apiPermissionIds"] = [
            str(permission.id) for permission in api_permissions
        ]
        representation["apiPermissionCodes"] = [
            permission.code for permission in api_permissions
        ]
        representation["buttons"] = [
            {"id": button.id, "code": button.code, "desc": button.desc}
            for button in instance.buttons.all()
        ]
        representation["routeName"] = instance.name
        route_path = self._normalize_route_path(instance.path, instance.pid_id)
        representation["path"] = route_path
        representation["routePath"] = route_path
        representation["keepAlive"] = not instance.no_cache
        representation["alwaysShow"] = instance.always_show
        representation["showIcon"] = instance.show_icon
        representation["i18nKey"] = instance.i18n_key
        representation["iconType"] = instance.icon_type
        representation["multiTab"] = instance.multi_tab
        representation["fixedIndexInTab"] = instance.fixed_index_in_tab
        representation["href"] = instance.href
        representation["constant"] = instance.constant
        representation["query"] = instance.query
        representation["status"] = "1" if instance.is_active else "2"
        representation["hideInMenu"] = instance.hidden
        return representation


class DictTypeSerializer(StandardModelSerializer):
    class Meta:
        model = DictType
        fields = "__all__"

    def to_internal_value(self, data):
        mutable = data.copy()
        if "dictCode" in mutable and "dict_code" not in mutable:
            mutable["dict_code"] = mutable.get("dictCode")
        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["dictCode"] = instance.dict_code
        representation["remark"] = instance.remark
        representation["createTime"] = instance.created_at
        representation["updateTime"] = instance.updated_at
        return representation


class DictItemSerializer(StandardModelSerializer):
    class Meta:
        model = DictItem
        fields = "__all__"

    def to_internal_value(self, data):
        mutable = data.copy()
        if "tagType" in mutable and "tag_type" not in mutable:
            mutable["tag_type"] = mutable.get("tagType") or DictItem.TagType.NONE
        if "dictCode" in mutable:
            mutable.pop("dictCode")
        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["dictCode"] = instance.dict_type.dict_code
        representation["tagType"] = instance.tag_type
        representation["createTime"] = instance.created_at
        representation["updateTime"] = instance.updated_at
        return representation


class SystemConfigSerializer(StandardModelSerializer):
    class Meta:
        model = SystemConfig
        fields = "__all__"

    def to_internal_value(self, data):
        mutable = data.copy()
        if "configName" in mutable and "config_name" not in mutable:
            mutable["config_name"] = mutable.get("configName")
        if "configKey" in mutable and "config_key" not in mutable:
            mutable["config_key"] = mutable.get("configKey")
        if "configValue" in mutable and "config_value" not in mutable:
            mutable["config_value"] = mutable.get("configValue")
        if "configGroup" in mutable and "config_group" not in mutable:
            mutable["config_group"] = mutable.get("configGroup")
        return super().to_internal_value(mutable)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["configName"] = instance.config_name
        representation["configKey"] = instance.config_key
        representation["configValue"] = instance.config_value
        representation["configGroup"] = instance.config_group
        representation["remark"] = instance.remark
        representation["createTime"] = instance.created_at
        representation["updateTime"] = instance.updated_at
        return representation
