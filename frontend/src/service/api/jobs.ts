import { createServiceConfig, getServiceBaseURL } from '@/utils/service';
import { request } from '../request';
import { getAuthorization } from '../request/shared';

/**
 * 任务执行域 API（T13/T14 契约）。
 *
 * - 唯一事件接口：GET runs/{id}/events?cursor=&limit=（sequence 游标）
 * - 取消/重试/重跑：POST runs/{id}/cancel | retry-failed | rerun
 * - WS：先 POST runs/{id}/realtime-ticket，再连接 /ws/jobs/runs/
 */

/** 后端分页响应（common.pagination） */
interface BackendPaginated<T> {
  list: T[];
  total: number;
  page: number;
  size: number;
}

const runPath = (domain: Api.Jobs.RunDomain): string => `/api/v1/${domain === 'ops' ? 'ops' : 'tasks'}/runs`;

function toRunQuery(params?: Api.Jobs.RunSearchParams) {
  const query: Record<string, string | number> = {};
  if (params?.current) query.pageNum = params.current;
  if (params?.size) query.pageSize = params.size;
  if (params?.status) query.status = params.status;
  if (params?.executionKind) query.executionKind = params.executionKind;
  if (params?.runDomain) query.runDomain = params.runDomain;
  if (params?.search) query.search = params.search;
  return query;
}

export async function fetchGetTaskRunList(params?: Api.Jobs.RunSearchParams) {
  const res = await request<BackendPaginated<Api.Jobs.RunRecord>>({
    url: runPath(params?.runDomain ?? 'task'),
    method: 'get',
    params: toRunQuery(params)
  });

  if (res.error) return res;
  return {
    ...res,
    data: { records: res.data.list, current: res.data.page, size: res.data.size, total: res.data.total }
  };
}

/** 运行详情 */
export async function fetchGetRunDetail(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.RunRecord>({
    signal,
    url: `${runPath(domain)}/${id}`,
    method: 'get'
  });
}

/** 运行节点状态 */
export async function fetchGetRunNodes(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.NodeRunRecord[]>({
    signal,
    url: `${runPath(domain)}/${id}/nodes`,
    method: 'get'
  });
}

/** 节点主机结果 */
export async function fetchGetNodeHostResults(nodeRunId: number, signal?: AbortSignal) {
  return request<Api.Jobs.HostResultRecord[]>({
    signal,
    url: `/api/v1/jobs/node-runs/${nodeRunId}/host-results`,
    method: 'get'
  });
}

/** 唯一事件接口：sequence 游标分页（T10 契约，after_id 已删除） */
export async function fetchGetRunEvents(
  id: number,
  cursor = 0,
  options: { domain: Api.Jobs.RunDomain; signal?: AbortSignal; limit?: number } = { domain: 'task' }
) {
  const { domain, signal, limit = 200 } = options;
  return request<Api.Jobs.RunEventPage>({
    signal,
    url: `${runPath(domain)}/${id}/events`,
    method: 'get',
    params: { cursor, limit }
  });
}

/** 取消运行（请求 cancel_requested，由 Runner 确认退出） */
export function fetchCancelRun(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.RunRecord>({
    signal,
    url: `${runPath(domain)}/${id}/cancel`,
    method: 'post'
  });
}

/** 重试失败运行（克隆新运行） */
export function fetchRetryFailedRun(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.RunRecord>({
    signal,
    url: `${runPath(domain)}/${id}/retry-failed`,
    method: 'post'
  });
}

/** 重跑已结束运行（克隆新运行） */
export function fetchRerunRun(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.RunRecord>({
    signal,
    url: `${runPath(domain)}/${id}/rerun`,
    method: 'post'
  });
}

/** 申请 WS 订阅票据（60 秒单次有效；未配置 Redis 时后端返回 503） */
export function fetchRealtimeTicket(id: number, domain: Api.Jobs.RunDomain = 'task', signal?: AbortSignal) {
  return request<Api.Jobs.RealtimeTicket>({
    signal,
    url: `${runPath(domain)}/${id}/realtime-ticket`,
    method: 'post'
  });
}

/** 快速命令执行（linux_shell / windows_powershell） */
export function fetchCreateQuickCommandRun(data: Api.Jobs.QuickCommandRunPayload) {
  return request<Api.Jobs.RunRecord>({
    url: '/api/v1/jobs/quick-commands/runs',
    method: 'post',
    data
  });
}

/** 工作流运行创建 */
export function fetchCreateWorkflowRun(data: Api.Jobs.WorkflowRunPayload) {
  return request<Api.Jobs.RunRecord>({
    url: '/api/v1/tasks/runs',
    method: 'post',
    data
  });
}

/** 已发布工作流版本（序列化器已输出 camelCase：inputSchema/workflowName/workflowCode） */
export function fetchPublishedWorkflowVersions() {
  return request<BackendPaginated<Api.Jobs.WorkflowVersionOption>>({
    url: '/api/v1/automation/workflow-versions',
    method: 'get',
    params: { status: 'published', pageNum: 1, pageSize: 100 }
  });
}

/**
 * 归档日志下载（GET 流式 text/plain，非 JSON envelope 协议）。
 * 后端直接返回 StreamingHttpResponse，需绕过扁平 request 实例用原生 fetch 接收 Blob。
 */
export async function fetchRunLogFile(
  id: number,
  domain: Api.Jobs.RunDomain = 'task',
  signal?: AbortSignal
): Promise<Blob | null> {
  const isHttpProxy = import.meta.env.DEV && import.meta.env.VITE_HTTP_PROXY === 'Y';
  const { baseURL } = getServiceBaseURL(import.meta.env, isHttpProxy);
  const response = await fetch(`${baseURL}${runPath(domain)}/${id}/log`, {
    headers: { Authorization: getAuthorization() ?? '' },
    signal
  });
  if (!response.ok) return null;
  return response.blob();
}

/** 资产主机选项（cmdb，AssetHostSerializer 已整体输出 camelCase） */
export function fetchGetHostOptions(keyword?: string) {
  return request<BackendPaginated<Api.Jobs.HostOption>>({
    url: '/api/v1/cmdb/hosts',
    method: 'get',
    params: { pageNum: 1, pageSize: 50, search: keyword }
  });
}

/** Worker 池选项（WorkerPoolSerializer 已输出 camelCase） */
export function fetchGetWorkerPools() {
  return request<BackendPaginated<Api.Jobs.WorkerPoolOption>>({
    url: '/api/v1/jobs/worker-pools',
    method: 'get',
    params: { pageNum: 1, pageSize: 50 }
  });
}

/** 运行日志 WS 地址：从服务基地址推导（http→ws），直连后端（vite 代理未配置 ws 转发） */
export function runEventWebSocketUrl() {
  const { baseURL } = createServiceConfig(import.meta.env);
  const url = new URL('/ws/jobs/runs/', new URL(baseURL || '/', window.location.origin));
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}
