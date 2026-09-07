"""pytest 全局夹具：提供 JWT 认证相关的可复用测试夹具。"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """未认证的 DRF API 客户端。"""
    return APIClient()


@pytest.fixture
def user(django_user_model):
    """普通测试用户。"""
    return django_user_model.objects.create_user(
        username="tester", password="test-pass-123"
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """携带有效 JWT access令牌的 API 客户端。"""
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return api_client
