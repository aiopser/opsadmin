import { request } from '../request';

export interface SecuritySubscription {
  id: number;
  name: string;
  enabled: boolean;
  interval_minutes: number;
  keywords: string[];
  severities: string[];
  notification: { templateId?: number; receivers?: string };
  initialized_at: string | null;
  last_attempt_at: string | null;
}
export interface SecurityAdvisory {
  id: number;
  stable_id: string;
  title: string;
  url: string;
  category: string;
  published: string;
  severity: string;
  source_status: string;
}
export interface SecurityCollection {
  id: number;
  subscription: number;
  status: 'queued' | 'running' | 'success' | 'failed';
  count: number;
  notifications: number;
  error: string;
  created_at: string;
}
export interface SecurityPage<T> {
  list: T[];
  total: number;
}
const base = '/api/v1/security';
export const getSecuritySubscriptions = () => request<SecuritySubscription[]>({ url: `${base}/subscriptions` });
export const saveSecuritySubscription = (
  data: Omit<SecuritySubscription, 'id' | 'initialized_at' | 'last_attempt_at'>,
  id?: number
) =>
  request<SecuritySubscription>({
    url: `${base}/subscriptions${id ? `/${id}` : ''}`,
    method: id ? 'put' : 'post',
    data
  });
export const collectSecuritySubscription = (id: number) =>
  request<SecurityCollection>({ url: `${base}/subscriptions/${id}/collect`, method: 'post' });
export type SecurityAdvisorySortField = 'stable_id' | 'title' | 'category' | 'source_status' | 'published';
export interface SecurityAdvisoryQuery {
  page: number;
  pageSize: number;
  sortBy: SecurityAdvisorySortField;
  order: 'asc' | 'desc';
}
export const getSecurityAdvisories = (query: SecurityAdvisoryQuery) =>
  request<SecurityPage<SecurityAdvisory>>({
    url: `${base}/advisories`,
    params: {
      pageNum: query.page,
      pageSize: query.pageSize,
      sortBy: query.sortBy,
      order: query.order
    }
  });
export const getSecurityCollections = () =>
  request<SecurityPage<SecurityCollection>>({ url: `${base}/collections`, params: { pageNum: 1, pageSize: 30 } });
