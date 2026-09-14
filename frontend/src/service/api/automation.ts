import { request } from '../request';

/**
 * 自动化资源域 API（automation）。
 *
 * - 命令原子：/api/v1/automation/commands（resource_kind 区分 command/script/playbook/module）
 * - 版本：/commands/{id}/versions（GET/POST）、/command-versions/{id}/publish|archive
 * - 工作流：/workflows、/workflow-versions（publish|archive）、/workflow-nodes、/workflow-edges
 * - 集成：/api-endpoints、/jenkins-servers、/notification-templates、/notification-channels
 * - 序列化器 fields="__all__" 输出 snake_case，请求体同样使用 snake_case
 */

/** 后端分页响应（common.pagination） */
interface BackendPaginated<T> {
  list: T[];
  total: number;
  page: number;
  size: number;
}

type PaginationData<T> = { records: T[]; current: number; size: number; total: number };

async function fetchPaginated<T>(url: string, params?: Record<string, unknown>) {
  const res = await request<BackendPaginated<T>>({ url, method: 'get', params });

  if (res.error) return res;
  return {
    ...res,
    data: {
      records: res.data.list,
      current: res.data.page,
      size: res.data.size,
      total: res.data.total
    } as PaginationData<T>
  };
}

function toPageQuery(params: { current: number; size: number; search?: string | null }) {
  const query: Record<string, string | number> = {};
  if (params.current) query.pageNum = params.current;
  if (params.size) query.pageSize = params.size;
  if (params.search) query.search = params.search;
  return query;
}

/** ============ 命令原子（command/script/playbook/module） ============ */

/** 命令原子列表 */
export function fetchGetCommandList(params?: Api.Automation.CommandSearchParams) {
  const query: Record<string, unknown> = toPageQuery(params ?? { current: 1, size: 10 });
  if (params?.status) query.status = params.status;
  if (params?.riskLevel) query.risk_level = params.riskLevel;
  if (params?.category) query.category = params.category;
  if (params?.resourceKind) query.resource_kind = params.resourceKind;
  return fetchPaginated<Api.Automation.CommandRecord>('/api/v1/automation/commands', query);
}

/** 新增命令原子 */
export function fetchAddCommand(data: Api.Automation.CommandPayload) {
  return request<Api.Automation.CommandRecord>({
    url: '/api/v1/automation/commands',
    method: 'post',
    data
  });
}

/** 更新命令原子 */
export function fetchUpdateCommand(id: number, data: Partial<Api.Automation.CommandPayload>) {
  return request<Api.Automation.CommandRecord>({
    url: `/api/v1/automation/commands/${id}`,
    method: 'put',
    data
  });
}

/** 删除命令原子（被流程节点引用时后端会拒绝） */
export function fetchDeleteCommand(id: number) {
  return request<null>({ url: `/api/v1/automation/commands/${id}`, method: 'delete' });
}

/** 命令版本列表（GET /commands/{id}/versions） */
export function fetchGetCommandVersions(commandId: number) {
  return request<Api.Automation.CommandVersionRecord[]>({
    url: `/api/v1/automation/commands/${commandId}/versions`,
    method: 'get'
  });
}

/** 创建命令版本（POST /commands/{id}/versions） */
export function fetchAddCommandVersion(commandId: number, data: Omit<Api.Automation.CommandVersionPayload, 'command'>) {
  return request<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/commands/${commandId}/versions`,
    method: 'post',
    data
  });
}

/** 更新命令版本（PATCH /command-versions/{id}，后端仅允许非已发布版本修改） */
export function fetchUpdateCommandVersion(
  versionId: number,
  data: Partial<Omit<Api.Automation.CommandVersionPayload, 'command'>>
) {
  return request<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}`,
    method: 'patch',
    data
  });
}

/** 发布命令版本（POST /command-versions/{id}/publish） */
export function fetchPublishCommandVersion(versionId: number) {
  return request<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}/publish`,
    method: 'post'
  });
}

/** 归档命令版本（POST /command-versions/{id}/archive） */
export function fetchArchiveCommandVersion(versionId: number) {
  return request<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}/archive`,
    method: 'post'
  });
}

/** ============ 工作流模板与版本 ============ */

/** 工作流模板列表 */
export function fetchGetWorkflowTemplateList(params?: {
  current: number;
  size: number;
  search?: string | null;
  status?: string | null;
}) {
  const query: Record<string, unknown> = toPageQuery(params ?? { current: 1, size: 10 });
  if (params?.status) query.status = params.status;
  return fetchPaginated<Api.Automation.WorkflowTemplateRecord>('/api/v1/automation/workflows', query);
}

/** 新增工作流模板 */
export function fetchAddWorkflowTemplate(data: Api.Automation.WorkflowTemplatePayload) {
  return request<Api.Automation.WorkflowTemplateRecord>({
    url: '/api/v1/automation/workflows',
    method: 'post',
    data
  });
}

/** 更新工作流模板 */
export function fetchUpdateWorkflowTemplate(id: number, data: Partial<Api.Automation.WorkflowTemplatePayload>) {
  return request<Api.Automation.WorkflowTemplateRecord>({
    url: `/api/v1/automation/workflows/${id}`,
    method: 'put',
    data
  });
}

/** 删除工作流模板 */
export function fetchDeleteWorkflowTemplate(id: number) {
  return request<null>({ url: `/api/v1/automation/workflows/${id}`, method: 'delete' });
}

/** 工作流版本列表（GET /workflow-versions?workflow={id}） */
export function fetchGetWorkflowVersions(workflowId: number) {
  return request<Api.Automation.WorkflowVersionRecord[]>({
    url: '/api/v1/automation/workflow-versions',
    method: 'get',
    params: { workflow: workflowId }
  });
}

/** 发布工作流版本（POST /workflow-versions/{id}/publish） */
export function fetchPublishWorkflowVersion(versionId: number) {
  return request<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}/publish`,
    method: 'post'
  });
}

/** 归档工作流版本（POST /workflow-versions/{id}/archive） */
export function fetchArchiveWorkflowVersion(versionId: number) {
  return request<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}/archive`,
    method: 'post'
  });
}

/** 创建草稿版本（POST /workflows/{id}/versions，版本号自动自增） */
export function fetchCreateWorkflowVersionDraft(workflowId: number) {
  return request<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflows/${workflowId}/versions`,
    method: 'post',
    data: {}
  });
}

/** 读取版本图协议（GET /workflow-versions/{id}/graph） */
export function fetchGetWorkflowGraph(versionId: number) {
  return request<{ graph: Api.Automation.WorkflowGraph; validationReport: string[] | null }>({
    url: `/api/v1/automation/workflow-versions/${versionId}/graph`,
    method: 'get'
  });
}

/** 整体保存版本图协议（PUT /workflow-versions/{id}/graph，仅草稿可写；校验失败返回 valid:false + errors） */
export function fetchUpdateWorkflowGraph(versionId: number, graph: Api.Automation.WorkflowGraph) {
  return request<{ valid: boolean; errors: string[]; graph: Api.Automation.WorkflowGraph }>({
    url: `/api/v1/automation/workflow-versions/${versionId}/graph`,
    method: 'put',
    data: { graph }
  });
}

/** 校验工作流版本（POST /workflow-versions/{id}/validate，返回发布前资源绑定检查结果） */
export function fetchValidateWorkflowVersion(versionId: number) {
  return request<{ valid: boolean; errors: string[] }>({
    url: `/api/v1/automation/workflow-versions/${versionId}/validate`,
    method: 'post'
  });
}

/** 更新工作流版本全局信息（PATCH /workflow-versions/{id}，仅草稿；graph 接口不写 inputSchema/globalVars） */
export function fetchUpdateWorkflowVersion(
  versionId: number,
  data: { inputSchema?: Record<string, unknown>; globalVars?: Record<string, unknown> }
) {
  return request<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}`,
    method: 'patch',
    data
  });
}

/** 工作流节点列表（GET /workflow-nodes?workflow_version={id}） */
export function fetchGetWorkflowNodes(versionId: number) {
  return request<Api.Automation.WorkflowNodeRecord[]>({
    url: '/api/v1/automation/workflow-nodes',
    method: 'get',
    params: { workflow_version: versionId }
  });
}

/** 工作流边列表（GET /workflow-edges?workflow_version={id}） */
export function fetchGetWorkflowEdges(versionId: number) {
  return request<Api.Automation.WorkflowEdgeRecord[]>({
    url: '/api/v1/automation/workflow-edges',
    method: 'get',
    params: { workflow_version: versionId }
  });
}

/** ============ 集成资源 ============ */

/** API 端点列表 */
export function fetchGetApiEndpointList(params?: { current: number; size: number; search?: string | null }) {
  return fetchPaginated<Api.Automation.ApiEndpointRecord>(
    '/api/v1/automation/api-endpoints',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增 API 端点 */
export function fetchAddApiEndpoint(data: Api.Automation.ApiEndpointPayload) {
  return request<Api.Automation.ApiEndpointRecord>({
    url: '/api/v1/automation/api-endpoints',
    method: 'post',
    data
  });
}

/** 更新 API 端点 */
export function fetchUpdateApiEndpoint(id: number, data: Partial<Api.Automation.ApiEndpointPayload>) {
  return request<Api.Automation.ApiEndpointRecord>({
    url: `/api/v1/automation/api-endpoints/${id}`,
    method: 'put',
    data
  });
}

/** 删除 API 端点 */
export function fetchDeleteApiEndpoint(id: number) {
  return request<null>({ url: `/api/v1/automation/api-endpoints/${id}`, method: 'delete' });
}

/** Jenkins 服务列表 */
export function fetchGetJenkinsServerList(params?: { current: number; size: number; search?: string | null }) {
  return fetchPaginated<Api.Automation.JenkinsServerRecord>(
    '/api/v1/automation/jenkins-servers',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增 Jenkins 服务 */
export function fetchAddJenkinsServer(data: Api.Automation.JenkinsServerPayload) {
  return request<Api.Automation.JenkinsServerRecord>({
    url: '/api/v1/automation/jenkins-servers',
    method: 'post',
    data
  });
}

/** 更新 Jenkins 服务 */
export function fetchUpdateJenkinsServer(id: number, data: Partial<Api.Automation.JenkinsServerPayload>) {
  return request<Api.Automation.JenkinsServerRecord>({
    url: `/api/v1/automation/jenkins-servers/${id}`,
    method: 'put',
    data
  });
}

/** 删除 Jenkins 服务 */
export function fetchDeleteJenkinsServer(id: number) {
  return request<null>({ url: `/api/v1/automation/jenkins-servers/${id}`, method: 'delete' });
}

/** Jenkins 任务列表（流程编排 jenkins 步骤引用） */
export function fetchGetJenkinsJobList(params?: { current: number; size: number; search?: string | null }) {
  return fetchPaginated<Api.Automation.JenkinsJobRecord>(
    '/api/v1/automation/jenkins-jobs',
    toPageQuery(params ?? { current: 1, size: 100 })
  );
}

/** 通知模板列表 */
export function fetchGetNotificationTemplateList(params?: { current: number; size: number; search?: string | null }) {
  return fetchPaginated<Api.Automation.NotificationTemplateRecord>(
    '/api/v1/automation/notification-templates',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增通知模板 */
export function fetchAddNotificationTemplate(data: Api.Automation.NotificationTemplatePayload) {
  return request<Api.Automation.NotificationTemplateRecord>({
    url: '/api/v1/automation/notification-templates',
    method: 'post',
    data
  });
}

/** 更新通知模板 */
export function fetchUpdateNotificationTemplate(id: number, data: Partial<Api.Automation.NotificationTemplatePayload>) {
  return request<Api.Automation.NotificationTemplateRecord>({
    url: `/api/v1/automation/notification-templates/${id}`,
    method: 'put',
    data
  });
}

/** 删除通知模板 */
export function fetchDeleteNotificationTemplate(id: number) {
  return request<null>({ url: `/api/v1/automation/notification-templates/${id}`, method: 'delete' });
}

/** 通知渠道列表（模板表单的渠道下拉数据源） */
export function fetchGetNotificationChannels() {
  return request<Api.Automation.NotificationChannelRecord[]>({
    url: '/api/v1/automation/notification-channels',
    method: 'get'
  });
}
