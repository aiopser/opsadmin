"""Large host runs use a paged list and load one host's output on demand."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.jobs.models import HostRunResult, NodeRun, WorkerPool, WorkflowRun
from apps.jobs.views import HostRunResultViewSet, NodeRunViewSet


class HostResultsPaginationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="host-results-owner",
            password="test-password",
            email="host-results@example.com",
            phone="13800000010",
        )
        pool = WorkerPool.objects.create(
            code="host-results", name="Host results", queue_name="ansible.host-results"
        )
        run = WorkflowRun.objects.create(worker_pool=pool, triggered_by=self.user)
        self.node = NodeRun.objects.create(workflow_run=run, node_key="work")
        HostRunResult.objects.bulk_create(
            HostRunResult(
                node_run=self.node,
                host_key=f"name:web-{index:03d}",
                hostname=f"web-{index:03d}",
                ip=f"10.0.0.{index}",
                status="failed" if index % 5 == 0 else "ok",
                stdout=f"private-output-{index}",
            )
            for index in range(1, 56)
        )
        self.factory = APIRequestFactory()

    def _get(self, path, view, pk):
        request = self.factory.get(path)
        force_authenticate(request, user=self.user)
        return view(request, pk=pk)

    def test_list_is_paginated_and_omits_large_output(self):
        view = NodeRunViewSet.as_view({"get": "host_results"})
        response = self._get(
            "/api/v1/jobs/node-runs/%s/host-results?pageNum=2&pageSize=20&hostStatus=all"
            % self.node.pk,
            view,
            self.node.pk,
        )
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual((data["total"], data["page"], len(data["list"])), (55, 2, 20))
        self.assertEqual(data["summary"], {"total": 55, "success": 44, "failed": 11})
        self.assertNotIn("stdout", data["list"][0])
        self.assertNotIn("stderr", data["list"][0])
        self.assertNotIn("rawEventData", data["list"][0])

    def test_filter_search_and_single_host_output(self):
        view = NodeRunViewSet.as_view({"get": "host_results"})
        response = self._get(
            "/api/v1/jobs/node-runs/%s/host-results?hostStatus=failed&hostSearch=web-010&pageSize=20"
            % self.node.pk,
            view,
            self.node.pk,
        )
        data = response.data["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["list"][0]["hostname"], "web-010")
        detail = self._get(
            "/api/v1/jobs/host-results/%s" % data["list"][0]["id"],
            HostRunResultViewSet.as_view({"get": "retrieve"}),
            data["list"][0]["id"],
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["data"]["stdout"], "private-output-10")

    def test_other_user_cannot_search_this_nodes_hosts(self):
        other = get_user_model().objects.create_user(
            username="other-host-viewer",
            password="test-password",
            email="other-host-viewer@example.com",
            phone="13800000011",
        )
        request = self.factory.get(
            f"/api/v1/jobs/node-runs/{self.node.pk}/host-results?hostSearch=web-010"
        )
        force_authenticate(request, user=other)
        response = NodeRunViewSet.as_view({"get": "host_results"})(
            request, pk=self.node.pk
        )
        self.assertIn(response.status_code, (403, 404))
