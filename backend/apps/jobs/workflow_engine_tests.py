from common.workflow.node_types import NodeType
from django.contrib.auth import get_user_model
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.automation.models import (
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool

from .models import NodeRun, NodeRunAttempt, WorkflowRun
from apps.jobs.application.runs import create_workflow_run
from .workflow_engine import node_queue_name, plan_dispatch


class WorkflowQueueRoutingTests(SimpleTestCase):
    def setUp(self):
        self.worker_pool = SimpleNamespace(queue_name="ansible.region", is_active=True)

    def test_ansible_nodes_use_worker_pool_queue(self):
        self.assertEqual(
            node_queue_name(
                NodeType.COMMAND,
                self.worker_pool,
                WorkflowRun.RunDomain.TASK,
            ),
            "ansible.region",
        )

    def test_non_ansible_nodes_use_task_domain_queue(self):
        self.assertEqual(
            node_queue_name(
                NodeType.API,
                self.worker_pool,
                WorkflowRun.RunDomain.TASK,
            ),
            "task",
        )

    def test_non_ansible_nodes_use_ops_domain_queue(self):
        self.assertEqual(
            node_queue_name(
                NodeType.API,
                self.worker_pool,
                WorkflowRun.RunDomain.OPS,
            ),
            "ops",
        )


class WorkflowGraphRuntimeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="graph-runner",
            password="test-password",
            phone="13800000100",
        )
        self.worker_pool = WorkerPool.objects.create(
            code="graph",
            name="Graph Pool",
            queue_name="ansible",
            is_default=True,
        )
        self.host = AssetHost.objects.create(
            hostname="graph-host",
            primary_ip="10.10.0.10",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        from apps.permission.models import Permission, Role
        from apps.permission.services import sync_casbin_rules, CasbinEnforcerService

        role = Role.objects.create(name="graph-assets")
        role.permission.add(
            Permission.objects.create(
                name="Graph assets",
                code="test.graph.assets",
                type="api",
                path="/api/v1/cmdb/hosts/:id",
                method="GET",
            )
        )
        role.permission.add(
            Permission.objects.create(
                name="Graph pool",
                code="test.graph.pool",
                type="api",
                path="/api/v1/jobs/worker-pools/:id",
                method="GET",
            )
        )
        self.user.role.add(role)
        sync_casbin_rules()
        CasbinEnforcerService.reload()
        self.sequence = 0

    def create_graph_run(self, nodes, edges, input_vars=None):
        self.sequence += 1
        workflow = WorkflowTemplate.objects.create(
            name=f"Graph {self.sequence}",
            code=f"graph_{self.sequence}",
            status=WorkflowTemplate.Status.PUBLISHED,
            created_by=self.user,
            updated_by=self.user,
        )
        version = WorkflowVersion.objects.create(
            workflow=workflow,
            version=1,
            status=WorkflowVersion.Status.DRAFT,
            created_by=self.user,
            published_by=self.user,
        )
        for index, item in enumerate(nodes):
            WorkflowNode.objects.create(
                workflow_version=version,
                node_key=item["id"],
                name=item.get("name") or item["id"],
                node_type=item["type"],
                resource_id=item.get("resourceId"),
                config=item.get("config") or {},
                retry_policy=item.get("retryPolicy") or {},
                failure_policy=item.get("failurePolicy")
                or WorkflowNode.FailurePolicy.STOP,
                order_index=index,
                timeout_seconds=60,
            )
        from apps.automation.models import WorkflowEdge

        node_map = {node.node_key: node for node in version.nodes.all()}
        for edge in edges:
            WorkflowEdge.objects.create(
                workflow_version=version,
                edge_key=edge["id"],
                source_node=node_map[edge["source"]],
                target_node=node_map[edge["target"]],
                condition_expression=edge.get("condition", ""),
                is_default=edge.get("isDefault", False),
            )
        version.publish(self.user)
        return create_workflow_run(
            workflow_version=version,
            target_hosts=[self.host],
            input_vars=input_vars or {},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

    def test_conditional_branch_and_default_join_only_selected_paths(self):
        for environment, chosen in (("test", "a"), ("other", "b")):
            with self.subTest(environment=environment):
                run = self.create_graph_run(
                    nodes=[
                        {"id": key, "type": kind}
                        for key, kind in (
                            ("start", "start"),
                            ("split", "parallel_gateway"),
                            ("a", "command"),
                            ("b", "command"),
                            ("join", "parallel_join"),
                            ("end", "end"),
                        )
                    ],
                    edges=[
                        {"id": "start_split", "source": "start", "target": "split"},
                        {
                            "id": "split_a",
                            "source": "split",
                            "target": "a",
                            "condition": "inputs.environment == 'test'",
                        },
                        {
                            "id": "split_b",
                            "source": "split",
                            "target": "b",
                            "isDefault": True,
                        },
                        {"id": "a_join", "source": "a", "target": "join"},
                        {"id": "b_join", "source": "b", "target": "join"},
                        {"id": "join_end", "source": "join", "target": "end"},
                    ],
                    input_vars={"environment": environment},
                )
                [node_id] = plan_dispatch(run.id)
                node = NodeRun.objects.get(pk=node_id)
                self.assertEqual(node.node_key, chosen)
                node.status = NodeRun.Status.SUCCESS
                node.save(update_fields=["status"])
                self.assertEqual(plan_dispatch(run.id), [])
                run.refresh_from_db()
                self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
                self.assertEqual(
                    run.node_runs.get(node_key="b" if chosen == "a" else "a").status,
                    NodeRun.Status.SKIPPED,
                )

    def test_parallel_join_waits_for_all_branches(self):
        run = self.create_graph_run(
            nodes=[
                {"id": "start", "type": "start"},
                {"id": "split", "type": "parallel_gateway"},
                {"id": "a", "type": "command"},
                {"id": "b", "type": "command"},
                {"id": "join", "type": "parallel_join"},
                {"id": "end", "type": "end"},
            ],
            edges=[
                {"id": "start_split", "source": "start", "target": "split"},
                {"id": "split_a", "source": "split", "target": "a"},
                {"id": "split_b", "source": "split", "target": "b"},
                {"id": "a_join", "source": "a", "target": "join"},
                {"id": "b_join", "source": "b", "target": "join"},
                {"id": "join_end", "source": "join", "target": "end"},
            ],
        )

        queued_ids = plan_dispatch(run.id)
        self.assertEqual(
            set(
                NodeRun.objects.filter(id__in=queued_ids).values_list(
                    "node_key", flat=True
                )
            ),
            {"a", "b"},
        )
        NodeRun.objects.filter(workflow_run=run, node_key="a").update(
            status=NodeRun.Status.SUCCESS
        )
        plan_dispatch(run.id)
        self.assertEqual(
            NodeRun.objects.get(workflow_run=run, node_key="join").status,
            NodeRun.Status.PENDING,
        )

        NodeRun.objects.filter(workflow_run=run, node_key="b").update(
            status=NodeRun.Status.SUCCESS
        )
        self.assertEqual(plan_dispatch(run.id), [])

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.SUCCESS)
        self.assertEqual(
            NodeRun.objects.get(workflow_run=run, node_key="join").status,
            NodeRun.Status.SUCCESS,
        )

    def test_worker_pool_concurrency_limits_parallel_ansible_nodes(self):
        self.worker_pool.concurrency_limit = 1
        self.worker_pool.queue_name = "ansible.region"
        self.worker_pool.save(
            update_fields=["concurrency_limit", "queue_name", "updated_at"]
        )
        run = self.create_graph_run(
            nodes=[
                {"id": "start", "type": "start"},
                {"id": "split", "type": "parallel_gateway"},
                {"id": "a", "type": "command"},
                {"id": "b", "type": "command"},
                {"id": "join", "type": "parallel_join"},
                {"id": "end", "type": "end"},
            ],
            edges=[
                {"id": "start_split", "source": "start", "target": "split"},
                {"id": "split_a", "source": "split", "target": "a"},
                {"id": "split_b", "source": "split", "target": "b"},
                {"id": "a_join", "source": "a", "target": "join"},
                {"id": "b_join", "source": "b", "target": "join"},
                {"id": "join_end", "source": "join", "target": "end"},
            ],
        )

        first_ids = plan_dispatch(run.id)
        self.assertEqual(len(first_ids), 1)
        first = NodeRun.objects.get(id=first_ids[0])
        first.status = NodeRun.Status.SUCCESS
        first.save(update_fields=["status", "updated_at"])

        second_ids = plan_dispatch(run.id)
        self.assertEqual(len(second_ids), 1)
        self.assertNotEqual(second_ids[0], first.id)
        attempts = NodeRunAttempt.objects.filter(node_run__workflow_run=run)
        self.assertEqual(
            set(attempts.values_list("queue_name", flat=True)),
            {"ansible.region"},
        )

    def test_retry_policy_creates_one_new_attempt(self):
        run = self.create_graph_run(
            nodes=[
                {"id": "start", "type": "start"},
                {
                    "id": "deploy",
                    "type": "command",
                    "failurePolicy": "retry",
                    "retryPolicy": {"maxAttempts": 2},
                },
                {"id": "end", "type": "end"},
            ],
            edges=[
                {"id": "start_deploy", "source": "start", "target": "deploy"},
                {"id": "deploy_end", "source": "deploy", "target": "end"},
            ],
        )
        [node_run_id] = plan_dispatch(run.id)
        node_run = NodeRun.objects.get(id=node_run_id)
        node_run.status = NodeRun.Status.FAILED
        node_run.failure_reason = "temporary failure"
        node_run.save(update_fields=["status", "failure_reason", "updated_at"])

        self.assertEqual(plan_dispatch(run.id), [node_run.id])

        node_run.refresh_from_db()
        self.assertEqual(node_run.status, NodeRun.Status.QUEUED)
        self.assertEqual(node_run.attempt_count, 2)
        self.assertEqual(
            NodeRunAttempt.objects.filter(node_run=node_run).count(),
            2,
        )
