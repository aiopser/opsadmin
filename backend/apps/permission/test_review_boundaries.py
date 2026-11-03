import pytest
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Menu, MenuButton, Permission, Role
from .serializers import MenuSerializer
from .services import sync_casbin_rules
from .views.role import RoleViewSet


@pytest.mark.django_db
@pytest.mark.parametrize("superuser", [False, True])
@pytest.mark.parametrize("builtin", [False, True])
def test_builtin_role_menu_assignment_requires_superuser(superuser, builtin):
    target = Role.objects.create(name="protected-review", is_system=builtin)
    original = Permission.objects.create(
        name="original",
        code="review.original",
        type="api",
        path="/api/original",
        method="GET",
    )
    target.permission.add(original)
    operator = Role.objects.create(name="operator-review")
    operator.permission.add(
        Permission.objects.create(
            name="assign",
            code="review.assign",
            type="api",
            path=f"/api/v1/roles/{target.pk}/menus",
            method="PUT",
        )
    )
    user = get_user_model().objects.create_user(
        username="operator", is_superuser=superuser
    )
    user.role.add(operator)
    sync_casbin_rules()
    request = APIRequestFactory().put(
        f"/api/v1/roles/{target.pk}/menus",
        {"menuIds": [], "buttonIds": [], "homePath": "changed"},
        format="json",
    )
    force_authenticate(request, user=user)
    response = RoleViewSet.as_view({"put": "menus"})(request, pk=str(target.pk))
    target.refresh_from_db()
    allowed = superuser or not builtin
    assert response.status_code == (200 if allowed else 403)
    assert target.permission.filter(pk=original.pk).exists() is (not allowed)
    if not allowed:
        assert target.home_path != "changed"


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["buttons", "perm"])
def test_menu_edit_cannot_convert_api_permission(field):
    permission = Permission.objects.create(
        name="read config",
        code="review.config",
        type="api",
        path="/api/config",
        method="GET",
    )
    menu = Menu.objects.create(
        name="Review",
        title="Before",
        menu_type="M",
        path="review",
        component="view.manage_config",
        order=1,
    )
    data = {
        "title": "After",
        field: [{"code": permission.code, "desc": "collision"}]
        if field == "buttons"
        else permission.code,
    }
    serializer = MenuSerializer(menu, data=data, partial=True)
    with pytest.raises(serializers.ValidationError):
        serializer.is_valid(raise_exception=True)
        serializer.save()
    permission.refresh_from_db()
    menu.refresh_from_db()
    assert (permission.type, permission.path, permission.method) == (
        "api",
        "/api/config",
        "GET",
    )
    assert menu.title == "Before"
    assert not menu.buttons.exists()


@pytest.mark.django_db
def test_button_code_cannot_take_another_menus_permission():
    first = Menu.objects.create(
        name="First",
        menu_type="M",
        path="first",
        component="view.manage_config",
        order=1,
    )
    second = Menu.objects.create(
        name="Second",
        menu_type="M",
        path="second",
        component="view.manage_config",
        order=2,
    )
    permission = Permission.objects.create(
        name="button", code="review.button", type="button"
    )
    button = MenuButton.objects.create(menu=first, code=permission.code, desc="first")
    button.permission.add(permission)
    serializer = MenuSerializer(
        second, data={"buttons": [{"code": permission.code}]}, partial=True
    )
    with pytest.raises(serializers.ValidationError):
        serializer.is_valid(raise_exception=True)
        serializer.save()
    assert not second.buttons.exists()
