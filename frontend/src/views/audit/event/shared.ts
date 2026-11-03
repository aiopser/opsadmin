import type { AuditEvent } from '@/service/api/audit';

type Locale = 'zh' | 'en';
type Label = Record<Locale, string>;

const resourceLabels: Record<string, Label> = {
  cloud_policy: { zh: '云采集策略', en: 'Cloud collection policy' },
  security_subscription: { zh: '漏洞订阅', en: 'Security subscription' },
  jumpserver_connection: { zh: 'JumpServer 连接', en: 'JumpServer connection' },
  enrollment_policy: { zh: '动态纳管策略', en: 'Enrollment policy' },
  monitoring_target: { zh: '监控目标', en: 'Monitoring target' },
  consul_connection: { zh: 'Consul 连接', en: 'Consul connection' },
  workflow_run: { zh: '执行记录', en: 'Run' },
  login: { zh: '登录账号', en: 'Login account' },
  workflow_task_ticket: { zh: '任务单', en: 'Task ticket' },
  workflow: { zh: '流程', en: 'Workflow' },
  workflow_version: { zh: '流程版本', en: 'Workflow version' },
  workflow_node: { zh: '流程步骤', en: 'Workflow step' },
  workflow_edge: { zh: '流程连接', en: 'Workflow connection' },
  command: { zh: '命令', en: 'Command' },
  command_version: { zh: '命令版本', en: 'Command version' },
  worker_pool: { zh: '执行池', en: 'Worker pool' },
  host: { zh: '主机资产', en: 'Host asset' },
  cmdb_host: { zh: '主机资产', en: 'Host asset' },
  host_group: { zh: '主机分组', en: 'Host group' },
  cmdb_host_group: { zh: '主机分组', en: 'Host group' },
  tag: { zh: '资产标签', en: 'Asset tag' },
  cmdb_host_tag: { zh: '资产标签', en: 'Asset tag' },
  credential: { zh: '凭据引用', en: 'Credential reference' },
  cmdb_credential_ref: { zh: '凭据引用', en: 'Credential reference' },
  asset_source: { zh: '资产来源', en: 'Asset source' },
  cmdb_asset_source: { zh: '资产来源', en: 'Asset source' },
  api_endpoint: { zh: 'API 接口', en: 'API endpoint' },
  jenkins_server: { zh: 'Jenkins 服务', en: 'Jenkins server' },
  jenkins_job: { zh: 'Jenkins 作业', en: 'Jenkins job' },
  git_repository: { zh: 'Git 仓库', en: 'Git repository' },
  notification_channel: { zh: '通知渠道', en: 'Notification channel' },
  notification_template: { zh: '通知模板', en: 'Notification template' }
};

const actionLabels: Record<string, Label> = {
  'auth.login.success': { zh: '登录成功', en: 'Login succeeded' },
  'auth.login.failure': { zh: '登录失败', en: 'Login failed' },
  'quick_command_run.create': { zh: '执行快速命令', en: 'Run quick command' },
  'playbook_run.create': { zh: '执行剧本', en: 'Run playbook' },
  'module_run.create': { zh: '执行模块', en: 'Run module' },
  'jobs.workflow_ticket.run': { zh: '执行任务单', en: 'Run task ticket' },
  'jobs.workflow_ticket.delete': { zh: '删除任务单', en: 'Delete task ticket' },
  'workflow_run.create': { zh: '启动执行', en: 'Start run' },
  'workflow_run.cancel': { zh: '取消执行', en: 'Cancel run' },
  'workflow_run.retry_failed': { zh: '重试失败步骤', en: 'Retry failed steps' },
  'workflow_run.rerun': { zh: '重新执行', en: 'Rerun' }
};

const verbLabels: Record<string, Label> = {
  create: { zh: '创建', en: 'Create' },
  update: { zh: '修改', en: 'Update' },
  delete: { zh: '删除', en: 'Delete' },
  publish: { zh: '发布', en: 'Publish' },
  run: { zh: '执行', en: 'Run' },
  test_send: { zh: '测试发送', en: 'Test send' },
  enable: { zh: '启用', en: 'Enable' },
  disable: { zh: '停用', en: 'Disable' }
};

const nameKeys = ['name', 'hostname', 'title', 'display_name', 'displayName'] as const;

export function getAuditResourceLabel(resourceType: string, locale: Locale): string {
  return resourceLabels[resourceType]?.[locale] ?? (locale === 'zh' ? '其他对象' : 'Other object');
}

function resolveActionLabel(event: Pick<AuditEvent, 'action' | 'resourceType'>, locale: Locale): string | null {
  const exact = actionLabels[event.action]?.[locale];
  if (exact) return exact;

  const verb = verbLabels[event.action.split('.').at(-1) ?? '']?.[locale];
  const resource = resourceLabels[event.resourceType]?.[locale];
  if (verb && resource) return locale === 'zh' ? `${verb}${resource}` : `${verb} ${resource.toLowerCase()}`;

  return null;
}

export function getAuditActionLabel(event: Pick<AuditEvent, 'action' | 'resourceType'>, locale: Locale): string {
  return resolveActionLabel(event, locale) ?? (locale === 'zh' ? '其他操作' : 'Other operation');
}

function getSnapshotName(snapshot: Record<string, unknown>): string | null {
  const name = nameKeys.map(key => snapshot[key]).find(value => typeof value === 'string' && value.trim());
  return typeof name === 'string' ? name.trim().slice(0, 80) : null;
}

export function getAuditObjectLabel(event: AuditEvent, locale: Locale): string {
  const resource = getAuditResourceLabel(event.resourceType, locale);
  const name = getSnapshotName(event.after ?? {}) ?? getSnapshotName(event.before ?? {});
  if (name) return `${resource} · ${name}`;
  if (event.resourceId) return `${resource} · ID ${event.resourceId}`;
  return resource;
}
