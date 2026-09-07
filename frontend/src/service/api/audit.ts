import type { FlatResponseData } from '@sa/axios';
import { request } from '../request';

/**
 * 审计事件（后端 DomainAuditEvent）
 * AuditEventSerializer 输出 snake_case 原始字段 + camelCase 别名，此处统一走 camelCase
 */
export interface AuditEvent {
  id: number;
  /** 领域：ops / task / automation / cmdb / security / system */
  domain: string;
  actor: number | null;
  /** 操作人用户名（未登录或已删除时为空串） */
  actorName: string;
  /** 动作标识，如 cmdb.host.create */
  action: string;
  /** 资源类型，如 host / workflow */
  resourceType: string;
  resourceId: string;
  /** 变更前快照 */
  before: Record<string, unknown>;
  /** 变更后快照 */
  after: Record<string, unknown>;
  requestId: string;
  ipAddress: string | null;
  userAgent: string;
  createdAt: string;
}

export interface AuditEventSearchParams {
  current?: number;
  size?: number;
  /** 按领域精确过滤 */
  domain?: string | null;
  /** 按动作精确过滤 */
  action?: string | null;
  /** 按资源类型精确过滤 */
  resourceType?: string | null;
  /** 关键词（动作/资源类型/资源ID/操作人/IP/UA 模糊搜索） */
  keywords?: string | null;
}

/** 后端分页响应（common.pagination.StandardResultSetPagination） */
interface BackendPaginated<T> {
  list?: T[];
  result?: T[];
  total?: number;
  count?: number;
  page?: number;
  size?: number;
}

function toQuery(params?: AuditEventSearchParams) {
  const query: Record<string, string | number> = {};
  if (params?.current) query.pageNum = params.current;
  if (params?.size) query.pageSize = params.size;
  if (params?.domain) query.domain = params.domain;
  if (params?.action) query.action = params.action;
  if (params?.resourceType) query.resource_type = params.resourceType;
  if (params?.keywords) query.search = params.keywords;

  return query;
}

/**
 * 将 request 的扁平响应中的 data 做映射转换，
 * 保持 { data, error, response } 结构不变，供 useUIPaginatedTable 消费。
 */
function mapFlatResponse<R>(
  res: FlatResponseData<any, BackendPaginated<AuditEvent>>,
  mapper: (data: BackendPaginated<AuditEvent>) => R
): FlatResponseData<any, R> {
  if (res.error || res.data === null) {
    return { data: null, error: res.error, response: res.response } as FlatResponseData<any, R>;
  }

  return { data: mapper(res.data), error: null, response: res.response } as FlatResponseData<any, R>;
}

/** 后端分页结构/全量数组 → 前端 PaginatingQueryRecord */
function transformPaginated(raw: BackendPaginated<AuditEvent>): Api.Common.PaginatingQueryRecord<AuditEvent> {
  const records = Array.isArray(raw) ? raw : (raw.result ?? raw.list ?? []);
  const meta: BackendPaginated<AuditEvent> = Array.isArray(raw) ? ({} as BackendPaginated<AuditEvent>) : raw;

  return {
    records,
    current: meta.page ?? 1,
    size: meta.size ?? records.length,
    total: meta.total ?? meta.count ?? records.length
  };
}

/** 分页查询审计事件（默认按时间倒序） */
export async function fetchGetAuditEventList(params?: AuditEventSearchParams) {
  const res = await request<BackendPaginated<AuditEvent>>({
    url: '/api/v1/audit/events',
    method: 'get',
    params: toQuery(params)
  });

  return mapFlatResponse(res, transformPaginated);
}
