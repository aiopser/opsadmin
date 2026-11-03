import { request } from '../request';

export interface ConsulConnection {
  id: number;
  name: string;
  endpoint: string;
  datacenter: string;
  description: string;
  has_token: boolean;
  is_active: boolean;
}

export interface ConsulConnectionInput {
  name: string;
  endpoint: string;
  datacenter: string;
  description: string;
  token: string;
  is_active: boolean;
}

export interface ConsulService {
  id: string;
  name: string;
  address: string;
  port: number;
  health: string;
  tags: string[];
  meta: Record<string, string>;
  managed: boolean;
}

export interface CatalogInstance extends ConsulService {
  node: string;
  datacenter: string;
}

export interface ConsulKvValue {
  key: string;
  value: string;
  create_index: number;
  modify_index: number;
  lock_index: number;
  flags: number;
}

export type TargetKind = 'host' | 'mysql' | 'redis' | 'blackbox';
export interface MonitoringTargetInput {
  name: string;
  connection: number | undefined;
  host?: number | null;
  kind: TargetKind;
  address: string;
  port: number;
  tags: string[];
  meta: Record<string, string>;
  check_enabled: boolean;
  probe_target: string;
  probe_module: string;
  sync_interval_minutes: number;
  follow_host_address: boolean;
  address_source: 'internal' | 'external';
}

export interface MonitoringTarget extends MonitoringTargetInput {
  id: number;
  connection: number;
  connection_name: string;
  service_id: string;
  registered: boolean;
  registration_uncertain: boolean;
  sync_state: string;
  synced_at: string | null;
}

export interface MonitoringSyncRecord {
  id: number;
  target_name: string;
  operation: 'register' | 'deregister';
  status: string;
  error: string;
  created_at: string;
  finished_at: string | null;
  trigger: 'manual' | 'batch' | 'automatic';
}

interface Page<T> {
  list: T[];
  total: number;
  page: number;
  size: number;
}

const connections = '/api/v1/consul/connections';
const targets = '/api/v1/monitoring/targets';

export const getConsulConnections = () => request<ConsulConnection[]>({ url: connections });
export const saveConsulConnection = (id: number | undefined, data: ConsulConnectionInput) =>
  request<ConsulConnection>({
    url: id ? `${connections}/${id}` : connections,
    method: id ? 'put' : 'post',
    data
  });
export const deleteConsulConnection = (id: number) => request<null>({ url: `${connections}/${id}`, method: 'delete' });
export const testConsulConnection = (id: number) =>
  request<{ agent: string; datacenter: string }>({
    url: `${connections}/${id}/test`,
    method: 'post'
  });
export const getConsulServices = (id: number) => request<ConsulService[]>({ url: `${connections}/${id}/services` });
export const getConsulKvKeys = (id: number, prefix: string) =>
  request<{ keys: string[] }>({ url: `${connections}/${id}/kv`, params: { prefix } });
export const getConsulKvValue = (id: number, key: string) =>
  request<ConsulKvValue>({ url: `${connections}/${id}/kv-value`, params: { key } });
export const updateConsulKv = (id: number, key: string, value: string) =>
  request<{ ok: boolean }>({ url: `${connections}/${id}/kv-write`, method: 'post', data: { key, value } });
export const deleteConsulKv = (id: number, key: string) =>
  request<{ ok: boolean }>({ url: `${connections}/${id}/kv-delete`, method: 'delete', data: { key } });
export const getMonitoringTargets = (page: number, search: string) =>
  request<Page<MonitoringTarget>>({
    url: targets,
    params: { pageNum: page, pageSize: 20, search }
  });
export const saveMonitoringTarget = (id: number | undefined, data: MonitoringTargetInput) =>
  request<MonitoringTarget>({
    url: id ? `${targets}/${id}` : targets,
    method: id ? 'put' : 'post',
    data
  });
export const deleteMonitoringTarget = (id: number) => request<null>({ url: `${targets}/${id}`, method: 'delete' });
export const previewMonitoringTarget = (id: number) =>
  request<Record<string, unknown>>({ url: `${targets}/${id}/preview` });
export const syncMonitoringTarget = (id: number, operation: 'sync' | 'deregister') =>
  request<MonitoringSyncRecord>({
    url: `${targets}/${id}/${operation}`,
    method: 'post'
  });
export const getMonitoringRecords = (target: number, page: number) =>
  request<Page<MonitoringSyncRecord>>({
    url: '/api/v1/monitoring/sync-records',
    params: { target, pageNum: page, pageSize: 20 }
  });
export const getPrometheusConfig = (connection: number) =>
  request<{ config: string; note: string }>({
    url: `/api/v1/monitoring/connections/${connection}/prometheus-config`
  });

export const getMonitoringAlertRules = (connection: number) =>
  request<{ config: string; note: string }>({
    url: `/api/v1/monitoring/connections/${connection}/alert-rules`
  });

export const getConsulDatacenters = (connection: number) =>
  request<string[]>({ url: `${connections}/${connection}/datacenters` });
export const getCatalogServices = (connection: number, datacenter: string) =>
  request<{ name: string; tags: string[] }[]>({
    url: `${connections}/${connection}/catalog-services`,
    params: { datacenter }
  });
export const getCatalogInstances = (connection: number, query: { datacenter: string; service: string; page: number }) =>
  request<Page<CatalogInstance>>({
    url: `${connections}/${connection}/catalog-instances`,
    params: {
      datacenter: query.datacenter,
      service: query.service,
      pageNum: query.page,
      pageSize: 20
    }
  });

export interface HostImportInput {
  connection: number;
  host_ids: number[];
  address_source: 'internal' | 'external';
  port: number;
  sync_interval_minutes: number;
  follow_host_address: boolean;
}
export interface HostImportRow {
  host_id: number;
  name: string;
  address: string;
  action: 'create' | 'exists' | 'duplicate' | 'invalid';
  reason: string;
}
export interface HostImportPreview {
  rows: HostImportRow[];
  preview_token: string;
  create_count: number;
  skip_count: number;
}
export const previewHostImport = (data: HostImportInput) =>
  request<HostImportPreview>({
    url: `${targets}/host-import-preview`,
    method: 'post',
    data
  });
export const commitHostImport = (data: HostImportInput & { preview_token: string }) =>
  request<{
    created: number;
    skipped: number;
    delivery_failed: number;
    target_ids: number[];
  }>({ url: `${targets}/host-import`, method: 'post', data });

export interface ConsulTemplateFile {
  id: number;
  name: string;
  host: number;
  host_name: string;
  host_ip: string;
  path: string;
  content: string;
  reload_command: string;
  last_deploy_status: string;
  last_deploy_at: string | null;
  last_deploy_message: string;
  revision: string;
  last_deploy_run: number | null;
}

export interface ConsulTemplateFileInput {
  name: string;
  host: number | undefined;
  path: string;
  content: string;
  reload_command: string;
}

const templates = '/api/v1/consul/templates';

export const getConsulTemplates = () => request<ConsulTemplateFile[]>({ url: templates });
export const saveConsulTemplate = (id: number | undefined, data: ConsulTemplateFileInput) => {
  return request<ConsulTemplateFile>({
    url: id ? `${templates}/${id}` : templates,
    method: id ? 'put' : 'post',
    data
  });
};
export const deleteConsulTemplate = (id: number) => request<null>({ url: `${templates}/${id}`, method: 'delete' });
export const deployConsulTemplate = (id: number, readId: string) =>
  request<{ run_id: number }>({ url: `${templates}/${id}/deploy`, method: 'post', data: { read_id: readId } });

export interface ConsulRemoteRead {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'expired';
  exists: boolean | null;
  content: string | null;
  checksum: string;
  size: number;
  error: string;
}
export interface ConsulRemoteReadInput {
  host: number;
  path: string;
  template_id?: number;
  revision?: string;
}
export const requestConsulRemoteRead = (data: ConsulRemoteReadInput) =>
  request<ConsulRemoteRead>({ url: `${templates}/read-remote`, method: 'post', data });
export const getConsulRemoteRead = (id: string) =>
  request<ConsulRemoteRead>({ url: `${templates}/remote-reads/${id}` });
export const compareConsulRemoteRead = (readId: string, content: string) =>
  request<{ changed: boolean; diff: string }>({
    url: `${templates}/compare-remote`,
    method: 'post',
    data: { read_id: readId, content }
  });
