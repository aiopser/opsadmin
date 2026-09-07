import json
import re
from collections import OrderedDict

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from common.api.responses import api_ok_response, api_error_response
from common.api.schema import generate_crud_schema
from common.api.viewsets import StandardModelViewSet
from ..models import Menu
from ..services import build_grouped_menu_tree, infer_system_setting_category
from ..serializers import MenuSerializer

# 旧模板组件名 → (前端路由名, 前端路由路径, 前端组件)。
# 仅覆盖 soybean-admin 前端实际存在的页面（manage 模块），其余旧格式组件
# 在动态路由输出时由 __normalize_route_component 降级为无组件。
LEGACY_COMPONENT_TO_VIEW = {
    "system/user/index": ("manage_user", "/manage/user", "view.manage_user"),
    "system/role/index": ("manage_role", "/manage/role", "view.manage_role"),
    "system/menu/index": ("manage_menu", "/manage/menu", "view.manage_menu"),
    "system/dept/index": ("manage_dept", "/manage/dept", "view.manage_dept"),
    "system/dict/index": ("manage_dict", "/manage/dict", "view.manage_dict"),
    "system/log/index": ("manage_log", "/manage/log", "view.manage_log"),
    "system/config/index": ("manage_config", "/manage/config", "view.manage_config"),
}


@generate_crud_schema(verbose_name="菜单", tags=["菜单管理"])
class MenuViewSet(StandardModelViewSet):
    queryset = (
        Menu.objects.prefetch_related("permission", "permission__role", "buttons")
        .filter()
        .order_by("-id")
    )
    serializer_class = MenuSerializer
    ordering_fields = ("id", "order")
    filterset_fields = ("id", "pid", "menu_group", "menu_type", "is_active")
    search_fields = ("name", "title")

    def get_permissions(self):
        if getattr(self, "action", None) == "routes":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(summary="获取顶级菜单", tags=["菜单管理"])
    @action(methods=["GET"], detail=False,)
    def parent(self, request, *args, **kwargs):
        parent_queryset = self.get_queryset().filter(pid=None).order_by("order")
        serializer = self.get_serializer(parent_queryset, many=True)

        return api_ok_response(serializer.data)

    @extend_schema(summary="获取菜单树", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, )
    def tree(self, request, *args, **kwargs):
        queryset = self.__filter_tree_queryset(request, self.get_queryset())
        parent_queryset = queryset.filter(pid=None).order_by("order", "id")
        tree = [self.__format_table_node(menu, queryset) for menu in parent_queryset]
        return api_ok_response(self.__sorted(tree))

    @extend_schema(summary="获取分组菜单树", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="grouped-tree")
    def grouped_tree(self, request, *args, **kwargs):
        grouped = build_grouped_menu_tree(self.get_queryset(), self.__format_group_node)
        return api_ok_response(grouped)

    @extend_schema(summary="获取系统设置菜单分组", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="system-settings")
    def system_settings(self, request, *args, **kwargs):
        grouped = OrderedDict(
            [
                ("user", []),
                ("permission", []),
            ]
        )
        queryset = self.get_queryset().filter(
            menu_group=Menu.MenuGroup.SYSTEM, pid=None
        )
        system_root = queryset.first()
        category_queryset = (
            self.get_queryset().filter(pid=system_root).order_by("order", "id")
            if system_root
            else queryset.none()
        )
        for item in category_queryset:
            grouped[infer_system_setting_category(item)].append(
                self.__format_group_node(item, self.get_queryset())
            )
        return api_ok_response(grouped)

    @extend_schema(summary="获取当前用户可见菜单", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="mine")
    def mine(self, request, *args, **kwargs):
        queryset = self.__visible_queryset(request)
        grouped = build_grouped_menu_tree(
            queryset,
            lambda menu: self.__format_group_node(menu, queryset),
        )
        return api_ok_response(grouped)

    @extend_schema(summary="获取当前用户动态路由", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="routes")
    def routes(self, request, *args, **kwargs):
        """输出 soybean-admin 动态路由结构：{ routes: MenuRoute[], home }。

        MenuRoute 为嵌套树，meta 字段与前端 RouteMeta 对齐；
        component 约定为 `layout.xxx` / `view.xxx` / `layout.xxx$view.xxx`。
        """
        queryset = self.__visible_queryset(request)
        parent_queryset = queryset.filter(pid=None).order_by("order", "id")
        routes = [
            self.__format_route_node(menu, queryset) for menu in parent_queryset
        ]
        return api_ok_response(
            {
                "routes": routes,
                "home": self.__resolve_home_route(request),
            }
        )

    @extend_schema(summary="获取页面组件列表", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="pages")
    def pages(self, request, *args, **kwargs):
        """返回菜单数据中已使用的页面组件名（去掉 view. 前缀）。"""
        components = (
            self.get_queryset()
            .filter(menu_type=Menu.MenuType.MENU, is_active=True)
            .exclude(component__isnull=True)
            .exclude(component__in=("", "Layout", "ParentView"))
            .values_list("component", flat=True)
            .distinct()
        )
        pages = sorted(
            {
                component[len("view.") :]
                if component.startswith("view.")
                else component
                for component in components
            }
        )
        return api_ok_response(pages)

    def __resolve_home_route(self, request):
        """当前用户默认首页：取第一个配置了 home_path 的角色，否则 home。"""
        user = request.user
        home_path = (
            user.role.filter(is_active=True, home_path__isnull=False)
            .exclude(home_path="")
            .values_list("home_path", flat=True)
            .first()
        )
        return home_path or "home"

    @staticmethod
    def __normalize_route_component(component):
        """归一化组件标识以匹配 elegant-router 约定。

        - "Layout" → "layout.base"（旧数据一级目录）
        - "ParentView" → None（旧数据子目录，由子路由自身承载）
        - "layout.xxx" / "view.xxx" / "layout.xxx$view.xxx" → 原样
        - 其余旧模板组件（如 system/user/index）→ None（前端无对应页面，降级跳过）
        """
        if not component:
            return None
        if component == "Layout":
            return "layout.base"
        if component == "ParentView":
            return None
        if component.startswith(("layout.", "view.")):
            return component
        return None

    def __format_route_node(self, menu, queryset, parent_path=""):
        component = menu.component or ""
        legacy = LEGACY_COMPONENT_TO_VIEW.get(component)
        if legacy:
            # 命中映射：直接输出前端约定路由（名称/路径/组件），避免旧路径污染
            route_name, route_path, component = legacy
        else:
            route_path = menu.path or ""
            if route_path and not route_path.startswith(("http://", "https://")):
                if not route_path.startswith("/"):
                    route_path = f"{parent_path.rstrip('/')}/{route_path}"
                # 归一化：合并多余斜杠（如 "//system" → "/system"）
                route_path = re.sub(r"/{2,}", "/", route_path)
            # 路由 name 归一化：剥离斜杠/连字符，符合前端路由命名约定
            raw_name = menu.name or (route_path or "root")
            route_name = (
                raw_name.strip("/").replace("/", "_").replace("-", "_")
                or "root"
            )
            component = self.__normalize_route_component(component)
        meta = {
            "title": menu.title or menu.name or route_path,
            "order": menu.order,
        }
        if menu.i18n_key:
            meta["i18nKey"] = menu.i18n_key
        if menu.icon:
            if menu.icon_type == Menu.IconType.LOCAL:
                meta["localIcon"] = menu.icon
            else:
                meta["icon"] = menu.icon
        if menu.no_cache:
            meta["keepAlive"] = False
        if menu.constant:
            meta["constant"] = True
        if menu.href:
            meta["href"] = menu.href
        if menu.hidden:
            meta["hideInMenu"] = True
        if menu.active_menu:
            meta["activeMenu"] = menu.active_menu
        if menu.multi_tab:
            meta["multiTab"] = True
        if menu.fixed_index_in_tab is not None:
            meta["fixedIndexInTab"] = menu.fixed_index_in_tab
        if menu.query:
            meta["query"] = menu.query
        node = {
            "id": str(menu.id),
            "name": route_name,
            "path": route_path,
            "component": component,
            "meta": meta,
        }
        if menu.redirect:
            node["redirect"] = menu.redirect
        children_queryset = queryset.filter(pid=menu).order_by("order", "id")
        children = [
            self.__format_route_node(child_menu, queryset, parent_path=route_path)
            for child_menu in children_queryset
        ]
        if children:
            node["children"] = children
        return node

    @extend_schema(summary="获取菜单选项", tags=["菜单管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request, *args, **kwargs):
        queryset = self.get_queryset().order_by("order", "id")
        nodes = [self.__format_option_node(menu) for menu in queryset]
        tree = self.__build_option_tree(nodes)
        return api_ok_response(tree)

    @extend_schema(summary="获取菜单表单数据", tags=["菜单管理"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)

    def __format_res(self, data, many):
        if not many:
            meta = {
                "title": data["title"],
                "roles": data["roles"],
                "icon": data["icon"],
                "showIcon": data["showIcon"],
                "hidden": data["hidden"],
                "noCache": data["no_cache"],
                "keepAlive": not data["no_cache"],
                "breadcrumb": data["breadcrumb"],
                "affix": data["affix"],
                "alwaysShow": data["always_show"],
                "params": None,
            }
            if data["active_menu"]:
                meta["activeMenu"] = data["active_menu"]
            res_dic = {
                "order": data["order"],
                "path": data["path"],
                "component": data["component"],
                "name": data["name"] or data["path"],
                "redirect": data["redirect"],
                "hidden": data["hidden"],
                "alwaysShow": data["always_show"],
                "meta": meta,
            }
            return res_dic
        else:
            res_list = []
            for item in json.loads(json.dumps(data)):
                meta = {
                    "title": item["title"],
                    "roles": item["roles"],
                    "icon": item["icon"],
                    "showIcon": item["showIcon"],
                    "hidden": item["hidden"],
                    "noCache": item["no_cache"],
                    "keepAlive": not item["no_cache"],
                    "breadcrumb": item["breadcrumb"],
                    "affix": item["affix"],
                    "alwaysShow": item["always_show"],
                    "params": None,
                }
                if item["active_menu"]:
                    meta["activeMenu"] = item["active_menu"]
                res_dic = {
                    "order": item["order"],
                    "path": item["path"],
                    "component": item["component"],
                    "name": item["name"],
                    "redirect": item["redirect"],
                    "hidden": item["hidden"],
                    "alwaysShow": item["always_show"],
                    "meta": meta,
                }
                res_list.append(res_dic)
            return res_list

    def __sorted(self, data):
        new_data = sorted(data, key=lambda x: x["order"])

        for item_dic in new_data:
            item_dic["children"] = (
                []
                if not item_dic.get("children")
                else self.__sorted(item_dic["children"])
            )
        return new_data

    def __format_table_node(self, menu, queryset=None):
        formatted = self.get_serializer(menu, many=False).data
        base_queryset = queryset if queryset is not None else self.get_queryset()
        children_queryset = base_queryset.filter(pid=menu).order_by("order", "id")
        formatted["children"] = [
            self.__format_table_node(child_menu, base_queryset)
            for child_menu in children_queryset
        ]
        return formatted

    def __format_group_node(self, menu, queryset=None):
        menu_data = self.get_serializer(menu, many=False).data
        base_queryset = queryset if queryset is not None else self.get_queryset()
        children_queryset = base_queryset.filter(pid=menu).order_by("order", "id")
        formatted = self.__format_res(menu_data, many=False)
        formatted["menuGroup"] = menu.menu_group
        formatted["systemCategory"] = menu_data.get("system_category")
        formatted["children"] = [
            self.__format_group_node(child_menu, base_queryset)
            for child_menu in children_queryset
        ]
        return formatted

    def __visible_queryset(self, request):
        user = request.user
        queryset = self.get_queryset()
        if getattr(user, "is_superuser", False):
            return queryset
        permission_ids = list(user.role.values_list("permission__id", flat=True))
        menu_ids = set(
            queryset.filter(permission__in=permission_ids).values_list("id", flat=True)
        )
        parent_map = dict(queryset.values_list("id", "pid_id"))
        visible_ids = set(menu_ids)
        for menu_id in list(menu_ids):
            parent_id = parent_map.get(menu_id)
            while parent_id:
                if parent_id in visible_ids:
                    break
                visible_ids.add(parent_id)
                parent_id = parent_map.get(parent_id)
        return queryset.filter(id__in=visible_ids).distinct()

    def __filter_tree_queryset(self, request, queryset):
        keywords = (request.query_params.get("keywords") or "").strip()
        if not keywords:
            return queryset
        matched_ids = set(
            queryset.filter(title__icontains=keywords).values_list("id", flat=True)
        ) | set(queryset.filter(name__icontains=keywords).values_list("id", flat=True))
        parent_map = dict(queryset.values_list("id", "pid_id"))
        visible_ids = set(matched_ids)
        for menu_id in list(matched_ids):
            parent_id = parent_map.get(menu_id)
            while parent_id:
                if parent_id in visible_ids:
                    break
                visible_ids.add(parent_id)
                parent_id = parent_map.get(parent_id)
        return queryset.filter(id__in=visible_ids)

    def __format_option_node(self, menu):
        return {
            "value": str(menu.id),
            "label": menu.title or menu.name or menu.path,
            "parentId": str(menu.pid_id) if menu.pid_id else "0",
            "type": menu.menu_type,
            "component": menu.component,
            "path": menu.path,
            "children": [],
        }

    def __build_option_tree(self, nodes):
        lookup = {node["value"]: node for node in nodes}
        roots = []
        for node in nodes:
            parent_id = node.get("parentId") or "0"
            if parent_id != "0" and parent_id in lookup:
                lookup[parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots
