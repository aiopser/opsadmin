import { request } from '../request';

/**
 * 自动化资源域 API（automation）。
 *
 * - 命令原子：/api/v1/automation/commands（resource_kind 区分 command/script/playbook/module）
 * - 版本：/commands/{id}/versions（GET/POST）、/command-versions/{id}/publish|archive
 * - 工作流：/workflows、/workflow-versions（publish|archive）、/workflow-nodes、/workflow-edges
 * - 集成：/api-endpoints、/jenkins-servers、/notification-templates、/notification-channels
 * - 命名约定：对外统一 camelCase。DRF 序列化器输出的 snake_case 由本层做「顶层 key」转换，
 *   请求体反向转换；嵌套业务 JSON（default_vars/argument_schema/config 等）内部是用户数据，不做递归转换。
 */

/** 后端分页响应（common.pagination） */
interface BackendPaginated<T> {
  list: T[];
  total: number;
  page: number;
  size: number;
}

type PaginationData<T> = { records: T[]; current: number; size: number; total: number };

/** snake_case → camelCase（仅顶层 key） */
function snakeToCamel(key: string): string {
  return key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

/** camelCase → snake_case（仅顶层 key） */
function camelToSnake(key: string): string {
  return key.replace(/[A-Z]/g, c => `_${c.toLowerCase()}`);
}

/** 对象顶层 key 转换（不递归，保护嵌套业务 JSON 内的用户数据） */
function convertTopKeys(obj: Record<string, unknown>, convert: (key: string) => string): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).map(([key, value]) => [convert(key), value]));
}

/** request<T> 的返回类型（FlatResponse 判别联合：success 时 data 非 null，fail 时 data 为 null） */
type FlatResult<T> = Awaited<ReturnType<typeof request<T>>>;

/** 包装响应：data 顶层 key 转 camelCase（兼容裸数组/分页等非对象 data） */
function withCamelData<T>(promise: Promise<FlatResult<T>>): Promise<FlatResult<T>> {
  return promise.then(res => {
    if (res.error || !res.data || typeof res.data !== 'object' || Array.isArray(res.data)) return res;
    return { ...res, data: convertTopKeys(res.data as Record<string, unknown>, snakeToCamel) as T };
  });
}

/** 包装数组响应：每条记录顶层 key 转 camelCase */
function withCamelList<T>(promise: Promise<FlatResult<T[]>>): Promise<FlatResult<T[]>> {
  return promise.then(res => {
    if (res.error || !Array.isArray(res.data)) return res;
    return { ...res, data: res.data.map(item => convertTopKeys(item as Record<string, unknown>, snakeToCamel)) as T[] };
  });
}

/** 包装请求：camelCase 载荷转 snake_case 后发送，响应转回 camelCase（DRF 序列化器接口专用） */
function serializerRequest<T>(config: {
  url: string;
  method: 'post' | 'put' | 'patch';
  data?: object;
}): Promise<FlatResult<T>> {
  const payload = config.data
    ? (convertTopKeys(config.data as Record<string, unknown>, camelToSnake) as Record<string, unknown>)
    : undefined;
  return withCamelData(request<Record<string, unknown>>({ ...config, data: payload })) as Promise<FlatResult<T>>;
}

/** 包装分页响应：list 内每条记录顶层 key 转 camelCase */
async function serializerPaginated<T>(
  url: string,
  params?: Record<string, unknown>
): Promise<FlatResult<PaginationData<T>>> {
  const res = await fetchPaginated<Record<string, unknown>>(url, params);
  if (res.error || !res.data) return res;
  return {
    ...res,
    data: {
      ...res.data,
      records: res.data.records.map(item => convertTopKeys(item, snakeToCamel))
    } as PaginationData<T>
  };
}

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
  return serializerPaginated<Api.Automation.CommandRecord>('/api/v1/automation/commands', query);
}

/** 新增命令原子 */
export function fetchAddCommand(data: Api.Automation.CommandPayload) {
  return serializerRequest<Api.Automation.CommandRecord>({
    url: '/api/v1/automation/commands',
    method: 'post',
    data
  });
}

/** 更新命令原子 */
export function fetchUpdateCommand(id: number, data: Partial<Api.Automation.CommandPayload>) {
  return serializerRequest<Api.Automation.CommandRecord>({
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
  return withCamelList<Api.Automation.CommandVersionRecord>(
    request({
      url: `/api/v1/automation/commands/${commandId}/versions`,
      method: 'get'
    })
  );
}

/** 创建命令版本（POST /commands/{id}/versions） */
export function fetchAddCommandVersion(commandId: number, data: Omit<Api.Automation.CommandVersionPayload, 'command'>) {
  return serializerRequest<Api.Automation.CommandVersionRecord>({
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
  return serializerRequest<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}`,
    method: 'patch',
    data
  });
}

/** 发布命令版本（POST /command-versions/{id}/publish） */
export function fetchPublishCommandVersion(versionId: number) {
  return serializerRequest<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}/publish`,
    method: 'post'
  });
}

/** 归档命令版本（POST /command-versions/{id}/archive） */
export function fetchArchiveCommandVersion(versionId: number) {
  return serializerRequest<Api.Automation.CommandVersionRecord>({
    url: `/api/v1/automation/command-versions/${versionId}/archive`,
    method: 'post'
  });
}

/** 删除命令版本（DELETE /command-versions/{id}，仅未被流程节点引用的版本可删） */
export function fetchDeleteCommandVersion(versionId: number) {
  return request<null>({
    url: `/api/v1/automation/command-versions/${versionId}`,
    method: 'delete'
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
  return serializerPaginated<Api.Automation.WorkflowTemplateRecord>('/api/v1/automation/workflows', query);
}

/** 新增工作流模板 */
export function fetchAddWorkflowTemplate(data: Api.Automation.WorkflowTemplatePayload) {
  return serializerRequest<Api.Automation.WorkflowTemplateRecord>({
    url: '/api/v1/automation/workflows',
    method: 'post',
    data
  });
}

/** 更新工作流模板 */
export function fetchUpdateWorkflowTemplate(id: number, data: Partial<Api.Automation.WorkflowTemplatePayload>) {
  return serializerRequest<Api.Automation.WorkflowTemplateRecord>({
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
  return serializerRequest<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}/publish`,
    method: 'post'
  });
}

/** 归档工作流版本（POST /workflow-versions/{id}/archive） */
export function fetchArchiveWorkflowVersion(versionId: number) {
  return serializerRequest<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}/archive`,
    method: 'post'
  });
}

/** 创建草稿版本（POST /workflows/{id}/versions，版本号自动自增） */
export function fetchCreateWorkflowVersionDraft(workflowId: number) {
  return serializerRequest<Api.Automation.WorkflowVersionRecord>({
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

/** 更新工作流版本全局信息（PATCH /workflow-versions/{id}，仅草稿；graph 接口不写 inputSchema） */
export function fetchUpdateWorkflowVersion(versionId: number, data: { inputSchema?: Record<string, unknown> }) {
  return request<Api.Automation.WorkflowVersionRecord>({
    url: `/api/v1/automation/workflow-versions/${versionId}`,
    method: 'patch',
    data
  });
}

/** 删除工作流版本（DELETE /workflow-versions/{id}，仅草稿可删） */
export function fetchDeleteWorkflowVersion(versionId: number) {
  return request<null>({
    url: `/api/v1/automation/workflow-versions/${versionId}`,
    method: 'delete'
  });
}

/** 工作流节点列表（GET /workflow-nodes?workflow_version={id}） */
export function fetchGetWorkflowNodes(versionId: number) {
  return withCamelList<Api.Automation.WorkflowNodeRecord>(
    request({
      url: '/api/v1/automation/workflow-nodes',
      method: 'get',
      params: { workflow_version: versionId }
    })
  );
}

/** 工作流边列表（GET /workflow-edges?workflow_version={id}） */
export function fetchGetWorkflowEdges(versionId: number) {
  return withCamelList<Api.Automation.WorkflowEdgeRecord>(
    request({
      url: '/api/v1/automation/workflow-edges',
      method: 'get',
      params: { workflow_version: versionId }
    })
  );
}

/** ============ 集成资源 ============ */

/** API 端点列表 */
export function fetchGetApiEndpointList(params?: { current: number; size: number; search?: string | null }) {
  return serializerPaginated<Api.Automation.ApiEndpointRecord>(
    '/api/v1/automation/api-endpoints',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增 API 端点 */
export function fetchAddApiEndpoint(data: Api.Automation.ApiEndpointPayload) {
  return serializerRequest<Api.Automation.ApiEndpointRecord>({
    url: '/api/v1/automation/api-endpoints',
    method: 'post',
    data
  });
}

/** 更新 API 端点 */
export function fetchUpdateApiEndpoint(id: number, data: Partial<Api.Automation.ApiEndpointPayload>) {
  return serializerRequest<Api.Automation.ApiEndpointRecord>({
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
  return serializerPaginated<Api.Automation.JenkinsServerRecord>(
    '/api/v1/automation/jenkins-servers',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增 Jenkins 服务 */
export function fetchAddJenkinsServer(data: Api.Automation.JenkinsServerPayload) {
  return serializerRequest<Api.Automation.JenkinsServerRecord>({
    url: '/api/v1/automation/jenkins-servers',
    method: 'post',
    data
  });
}

/** 更新 Jenkins 服务 */
export function fetchUpdateJenkinsServer(id: number, data: Partial<Api.Automation.JenkinsServerPayload>) {
  return serializerRequest<Api.Automation.JenkinsServerRecord>({
    url: `/api/v1/automation/jenkins-servers/${id}`,
    method: 'put',
    data
  });
}

/** 删除 Jenkins 服务 */
export function fetchDeleteJenkinsServer(id: number) {
  return request<null>({ url: `/api/v1/automation/jenkins-servers/${id}`, method: 'delete' });
}

/** 测试 Jenkins 连通性（未保存的表单值也可直接测试；编辑时 secret 留空则用存量 Token） */
export function fetchTestJenkinsServer(data: {
  id?: number;
  baseUrl: string;
  username: string;
  secret?: string;
  verifySsl?: boolean;
}) {
  return request<{ reachable: boolean }>({
    url: '/api/v1/automation/jenkins-servers/test-connection',
    method: 'post',
    data
  });
}

/** ============ Git 仓库 ============ */

/** Git 仓库列表 */
export function fetchGetGitRepositoryList(params?: { current: number; size: number; search?: string | null }) {
  return serializerPaginated<Api.Automation.GitRepositoryRecord>(
    '/api/v1/automation/git-repositories',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 新增 Git 仓库 */
export function fetchAddGitRepository(data: Api.Automation.GitRepositoryPayload) {
  return serializerRequest<Api.Automation.GitRepositoryRecord>({
    url: '/api/v1/automation/git-repositories',
    method: 'post',
    data
  });
}

/** 更新 Git 仓库 */
export function fetchUpdateGitRepository(id: number, data: Partial<Api.Automation.GitRepositoryPayload>) {
  return serializerRequest<Api.Automation.GitRepositoryRecord>({
    url: `/api/v1/automation/git-repositories/${id}`,
    method: 'put',
    data
  });
}

/** 删除 Git 仓库 */
export function fetchDeleteGitRepository(id: number) {
  return request<null>({ url: `/api/v1/automation/git-repositories/${id}`, method: 'delete' });
}

/** 列出 Git 仓库文件（供新建脚本/Playbook/Module 时选择） */
export function fetchGetGitRepositoryFiles(
  id: number,
  params?: { ref?: string; search?: string | null; limit?: number }
) {
  return request<Api.Automation.GitRepoFileEntry>({
    url: `/api/v1/automation/git-repositories/${id}/files`,
    method: 'get',
    params
  });
}

/** 加载 Git 仓库文件内容（导入到资源内容框） */
export function fetchLoadGitRepositoryFile(id: number, data: { path: string; ref?: string }) {
  return request<Api.Automation.GitRepoLoadResult>({
    url: `/api/v1/automation/git-repositories/${id}/load`,
    method: 'post',
    data
  });
}

/** Jenkins 任务列表（流程编排 jenkins 步骤引用） */
export function fetchGetJenkinsJobList(params?: {
  current: number;
  size: number;
  search?: string | null;
  server?: number;
}) {
  return serializerPaginated<Api.Automation.JenkinsJobRecord>(
    '/api/v1/automation/jenkins-jobs',
    toPageQuery(params ?? { current: 1, size: 100 })
  );
}

/** 同步指定 Jenkins 服务的任务列表（返回该服务当前活跃的任务） */
export function fetchSyncJenkinsJobs(id: number) {
  return request<Api.Automation.JenkinsJobRecord[]>({
    url: `/api/v1/automation/jenkins-servers/${id}/jobs`,
    method: 'get'
  });
}

/** 探测 Jenkins 任务定义的构建参数（供流程设计自动带出参数名） */
export function fetchGetJenkinsJobParameters(id: number) {
  return request<Api.Automation.JenkinsJobParameter[]>({
    url: `/api/v1/automation/jenkins-jobs/${id}/parameters`,
    method: 'get'
  });
}

/** 通知模板列表 */
export function fetchGetNotificationTemplateList(params?: { current: number; size: number; search?: string | null }) {
  return serializerPaginated<Api.Automation.NotificationTemplateRecord>(
    '/api/v1/automation/notification-templates',
    toPageQuery(params ?? { current: 1, size: 10 })
  );
}

/** 通知模板详情 */
export function fetchGetNotificationTemplate(id: number) {
  return withCamelData(
    request<Record<string, unknown>>({
      url: `/api/v1/automation/notification-templates/${id}`,
      method: 'get'
    })
  ) as Promise<FlatResult<Api.Automation.NotificationTemplateRecord>>;
}

/** 新增通知模板 */
export function fetchAddNotificationTemplate(data: Api.Automation.NotificationTemplatePayload) {
  return serializerRequest<Api.Automation.NotificationTemplateRecord>({
    url: '/api/v1/automation/notification-templates',
    method: 'post',
    data
  });
}

/** 更新通知模板 */
export function fetchUpdateNotificationTemplate(id: number, data: Partial<Api.Automation.NotificationTemplatePayload>) {
  return serializerRequest<Api.Automation.NotificationTemplateRecord>({
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
  return withCamelList<Api.Automation.NotificationChannelRecord>(
    request({
      url: '/api/v1/automation/notification-channels',
      method: 'get'
    })
  );
}

export function fetchAddNotificationChannel(data: Api.Automation.NotificationChannelPayload) {
  return serializerRequest<Api.Automation.NotificationChannelRecord>({
    url: '/api/v1/automation/notification-channels',
    method: 'post',
    data
  });
}

export function fetchUpdateNotificationChannel(id: number, data: Partial<Api.Automation.NotificationChannelPayload>) {
  return serializerRequest<Api.Automation.NotificationChannelRecord>({
    url: `/api/v1/automation/notification-channels/${id}`,
    method: 'patch',
    data
  });
}

export function fetchDeleteNotificationChannel(id: number) {
  return request<null>({ url: `/api/v1/automation/notification-channels/${id}`, method: 'delete' });
}

export function fetchGetNotificationRecords(params: { current: number; size: number }) {
  return serializerPaginated<Api.Automation.NotificationRecord>(
    '/api/v1/automation/notification-records',
    toPageQuery(params)
  );
}

export function fetchGetNotificationVariables(
  scenario: Api.Automation.NotificationScenario,
  workflowVersionId?: number | null
) {
  return request<Api.Automation.NotificationVariableCatalog>({
    url: '/api/v1/automation/notification-templates/variables',
    method: 'get',
    params: { scenario, workflowVersionId: workflowVersionId ?? undefined }
  });
}

export function fetchPreviewNotificationTemplate(data: Api.Automation.NotificationPreviewPayload) {
  return request<Api.Automation.NotificationPreviewResult>({
    url: '/api/v1/automation/notification-templates/preview',
    method: 'post',
    data
  });
}

export function fetchTestNotificationTemplate(id: number, data: Api.Automation.NotificationSample) {
  return request<{ workflowRunId: number; status: string }>({
    url: `/api/v1/automation/notification-templates/${id}/test-send`,
    method: 'post',
    data
  });
}
