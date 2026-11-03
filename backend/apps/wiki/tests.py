from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import WikiPage
from .views import WikiPageViewSet


class WikiPageApiTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = get_user_model().objects.create_superuser(
            username="wiki-admin", password="wiki-pass-123"
        )
        self.visitor = get_user_model().objects.create_user(
            username="wiki-visitor", password="wiki-pass-123"
        )

    def _request(self, method, path, action_name, user, pk=None, data=None):
        request = getattr(self.factory, method)(
            path, data, format="json" if data is not None else None
        )
        force_authenticate(request, user=user)
        view = WikiPageViewSet.as_view({method: action_name})
        return view(request, pk=pk) if pk else view(request)

    def test_tree_returns_flat_nodes_with_parent(self):
        folder = WikiPage.objects.create(title="运维手册", is_folder=True)
        child = WikiPage.objects.create(title="上线流程", parent=folder)

        response = self._request(
            "get", "/api/v1/wiki/pages/tree", "tree", self.admin
        )

        self.assertEqual(response.status_code, 200)
        nodes = response.data["data"]
        self.assertEqual({node["title"] for node in nodes}, {"运维手册", "上线流程"})
        child_node = next(node for node in nodes if node["id"] == child.id)
        self.assertEqual(child_node["parent"], folder.id)

    def test_tree_requires_seeded_permission(self):
        response = self._request(
            "get", "/api/v1/wiki/pages/tree", "tree", self.visitor
        )

        self.assertEqual(response.status_code, 403)

    def test_move_to_own_descendant_is_rejected(self):
        folder = WikiPage.objects.create(title="手册", is_folder=True)
        child = WikiPage.objects.create(title="章节", parent=folder)

        response = self._request(
            "put",
            f"/api/v1/wiki/pages/{folder.id}",
            "update",
            self.admin,
            pk=folder.id,
            data={"title": "手册", "parent": child.id},
        )

        self.assertEqual(response.status_code, 400)
        folder.refresh_from_db()
        self.assertIsNone(folder.parent_id)

    def test_delete_removes_children(self):
        folder = WikiPage.objects.create(title="手册", is_folder=True)
        WikiPage.objects.create(title="章节", parent=folder)

        response = self._request(
            "delete", f"/api/v1/wiki/pages/{folder.id}", "destroy", self.admin, pk=folder.id
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WikiPage.objects.count(), 0)
