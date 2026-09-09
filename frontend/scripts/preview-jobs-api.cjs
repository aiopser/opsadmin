// Isolated visual fixture. Binds only loopback; never opens a database or executes work.
const http = require('node:http');
const run = {
  id: 41,
  workflowName: '隔离演示流程',
  workflowVersion: 1,
  workerPoolName: '本地测试池',
  triggeredByName: 'preview',
  targetCount: 1,
  status: 'failed',
  run_domain: 'task',
  execution_kind: 'workflow',
  trigger_type: 'manual',
  started_at: '2026-09-09T10:00:00Z',
  duration_ms: 1200,
  failure_reason: '模拟失败，用于验证详情和重试界面',
  input_vars: {},
  context_vars: {},
  graph_snapshot: {},
  target_snapshot: [
    { host_id: 1, hostname: 'preview-host', address: '192.0.2.10', port: 22, connection_type: 'ssh', variables: {} }
  ]
};
const perms = [
  'jobs.workflow_run:read',
  'jobs.workflow_run:create',
  'jobs.workflow_run:cancel',
  'jobs.workflow_run:retry',
  'ops.workflow_run:read',
  'ops.workflow_run:cancel',
  'ops.workflow_run:retry',
  'jobs.quick_command:execute'
];
const paged = list => ({ list, page: 1, size: 10, total: list.length });
const routes = [
  {
    name: 'task',
    path: '/task',
    component: 'layout.base',
    meta: { title: '任务系统' },
    children: [
      { name: 'task_run', path: '/task/run', component: 'view.task_run', meta: { title: '任务列表' } },
      {
        name: 'task_run-detail',
        path: '/task/run-detail/:id',
        component: 'view.task_run-detail',
        meta: { title: '执行详情', hideInMenu: true }
      }
    ]
  },
  {
    name: 'ops',
    path: '/ops',
    component: 'layout.base',
    meta: { title: '作业系统' },
    children: [
      {
        name: 'ops_quick-execute',
        path: '/ops/quick-execute',
        component: 'view.ops_quick-execute',
        meta: { title: '快捷执行' }
      }
    ]
  }
];

http
  .createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:19527');
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }
    const path = new URL(req.url, 'http://127.0.0.1').pathname;
    let data = paged([]);
    if (path.endsWith('/auth/login')) data = { access: 'preview-only', refresh: 'preview-only' };
    else if (path.endsWith('/auth/me')) data = { id: 1, username: 'preview', roles: ['R_SUPER'], perms };
    else if (path.endsWith('/menus/routes')) data = { routes, home: 'task_run' };
    else if (path.endsWith('/events'))
      data = {
        events: [
          {
            id: 1,
            sequence: 1,
            event_type: 'node_failed',
            message: '模拟事件：执行失败',
            created_at: '2026-09-09T10:00:01Z'
          }
        ],
        next_cursor: 1,
        has_more: false,
        terminal: true,
        snapshot_version: 1
      };
    else if (path.endsWith('/nodes'))
      data = [
        {
          id: 7,
          nodeKey: 'check',
          nodeName: '检查',
          commandName: '隔离检查',
          node_type: 'command',
          status: 'failed',
          attempt_count: 1,
          exit_code: 1,
          duration_ms: 1200,
          failure_reason: '模拟失败'
        }
      ];
    else if (path.endsWith('/host-results'))
      data = [{ id: 1, hostname: 'preview-host', ip: '192.0.2.10', status: 'failed', rc: 1 }];
    else if (path.endsWith('/log')) {
      res.setHeader('Content-Type', 'text/plain');
      res.end('isolated preview output\n');
      return;
    } else if (path.endsWith('/hosts'))
      data = paged([
        { id: 1, hostname: 'preview-host', primary_ip: '192.0.2.10', os_family: 'linux', status: 'active' }
      ]);
    else if (path.endsWith('/worker-pools'))
      data = paged([
        { id: 1, name: '本地测试池', is_active: true, is_default: true, execution_kinds: ['workflow', 'quick_command'] }
      ]);
    else if (path.endsWith('/workflow-versions'))
      data = paged([
        {
          id: 1,
          workflowName: '隔离演示流程',
          workflowCode: 'preview',
          version: 1,
          input_schema: [{ name: 'service', label: '服务名称', type: 'string', required: true }]
        }
      ]);
    else if (/\/runs\/\d+/.test(path))
      data = {
        ...run,
        id: Number(path.match(/\/runs\/(\d+)/)[1]),
        run_domain: path.includes('/ops/') ? 'ops' : 'task'
      };
    else if (path.endsWith('/runs'))
      data =
        req.method === 'POST'
          ? { ...run, id: 42, status: 'pending' }
          : paged([{ ...run, run_domain: path.includes('/ops/') ? 'ops' : 'task' }]);
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ code: '00000', msg: 'isolated preview', data }));
  })
  .listen(18765, '127.0.0.1', () => console.log('Isolated preview API: 127.0.0.1:18765'));
