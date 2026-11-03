import { request } from '../request';

export interface EnrollmentPolicyInput {
  name: string;
  connection: number | undefined;
  scope: 'group' | 'rule';
  group: number | null;
  include_descendants: boolean;
  match_rule: Record<string, string | number | string[] | number[]>;
  address_source: 'internal' | 'external';
  port: number;
  interval_minutes: number;
  target_sync_interval_minutes: number;
  follow_host_address: boolean;
}
export interface EnrollmentPolicy extends EnrollmentPolicyInput {
  id: number;
  connection_name: string;
  group_name: string;
  actor_name: string;
  is_active: boolean;
  last_run_at: string | null;
}
export interface EnrollmentPreview {
  rows: { id: number; name: string; address: string }[];
  matched_count: number;
  existing_count: number;
  invalid_count: number;
  remaining_count: number;
  create_count: number;
  preview_token: string;
}
export interface EnrollmentRun {
  id: number;
  policy_name: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  trigger: 'manual' | 'automatic';
  error: string;
  summary: { created?: number; delivery_failed?: number; remaining?: number };
  created_at: string;
}
interface Page<T> {
  list: T[];
  total: number;
}
const base = '/api/v1/monitoring/enrollment-policies';
export const getEnrollmentPolicies = (page: number, search: string) =>
  request<Page<EnrollmentPolicy>>({ url: base, params: { pageNum: page, pageSize: 20, search } });
export const saveEnrollmentPolicy = (id: number | undefined, data: EnrollmentPolicyInput) =>
  request<EnrollmentPolicy>({ url: id ? `${base}/${id}` : base, method: id ? 'put' : 'post', data });
export const deleteEnrollmentPolicy = (id: number) => request<null>({ url: `${base}/${id}`, method: 'delete' });
export const previewEnrollmentPolicy = (id: number) => request<EnrollmentPreview>({ url: `${base}/${id}/preview` });
export const confirmEnrollmentPolicy = (id: number, data: { preview_token: string; operation: 'run' | 'enable' }) =>
  request<EnrollmentRun>({
    url: `${base}/${id}/${data.operation}`,
    method: 'post',
    data: { preview_token: data.preview_token }
  });
export const pauseEnrollmentPolicy = (id: number) =>
  request<EnrollmentPolicy>({ url: `${base}/${id}/pause`, method: 'post' });
export const getEnrollmentRuns = (policy: number, page: number) =>
  request<Page<EnrollmentRun>>({
    url: '/api/v1/monitoring/enrollment-runs',
    params: { policy, pageNum: page, pageSize: 20 }
  });
