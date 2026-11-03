import { request } from '../request';

export interface JumpServerConnection {
  id: number;
  name: string;
  endpoint: string;
  key_id: string;
  org_id: string;
  node_id: string;
  linux_platform: number;
  windows_platform: number;
  is_active: boolean;
  verify_tls: boolean;
  has_secret: boolean;
  sync_interval_minutes: number;
}
export type JumpServerInput = Omit<JumpServerConnection, 'id' | 'has_secret'> & { secret: string };
export interface JumpServerSnapshot {
  host_id: number;
  payload: {
    name: string;
    address: string;
    platform: number;
    protocols: { name: string; port: number }[];
    nodes: string[];
  };
}
export interface JumpServerRun {
  id: number;
  status: 'preview' | 'queued' | 'running' | 'succeeded' | 'failed';
  error: string;
  snapshot: JumpServerSnapshot[];
  created_at: string;
  results: { host_id: number; external_id: string; status: string }[];
}
const base = '/api/v1/integrations/jumpserver/connections';
export const fetchJumpServers = (search: string) => request<JumpServerConnection[]>({ url: base, params: { search } });
export const saveJumpServer = (data: JumpServerInput, id?: number) =>
  request<JumpServerConnection>({
    url: id ? `${base}/${id}` : base,
    method: id ? 'patch' : 'post',
    data: {
      name: data.name,
      endpoint: data.endpoint,
      key_id: data.key_id,
      secret: data.secret,
      org_id: data.org_id,
      node_id: data.node_id,
      linux_platform: data.linux_platform,
      windows_platform: data.windows_platform,
      is_active: data.is_active,
      verify_tls: data.verify_tls,
      sync_interval_minutes: data.sync_interval_minutes
    }
  });
export const deleteJumpServer = (id: number) => request({ url: `${base}/${id}`, method: 'delete' });
export const testJumpServer = (id: number) =>
  request<{ success: boolean }>({ url: `${base}/${id}/test`, method: 'post' });
export const previewJumpServer = (id: number, hostIds: number[]) =>
  request<JumpServerRun>({ url: `${base}/${id}/preview`, method: 'post', data: { host_ids: hostIds } });
export const confirmJumpServer = (id: number, previewId: number) =>
  request<JumpServerRun>({ url: `${base}/${id}/confirm`, method: 'post', data: { preview_id: previewId } });
export const fetchJumpServerRecords = (id: number) => request<JumpServerRun[]>({ url: `${base}/${id}/records` });
