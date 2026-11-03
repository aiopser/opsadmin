import { request } from '../request';

export interface ResourceTemplate {
  id: number;
  name: string;
  provider: 'aliyun' | 'tencent';
  description: string;
  is_active: boolean;
}

export interface ResourceVersion {
  id: number;
  template: number;
  number: number;
  status: 'draft' | 'published';
  constraints: {
    schemaVersion?: 2;
    selectors?: {
      sourceIds: number[];
      networkTags?: Record<string, string>;
      securityGroupTags?: Record<string, string>;
      imageSources?: string[];
      imageOs?: string[];
      imageNamePrefix?: string;
      cpuMin?: number;
      cpuMax?: number;
      memoryMinMiB?: number;
      memoryMaxMiB?: number;
      families?: string[];
    };
    regions: string[];
    bundle_digest?: string;
    allowed_image_ids?: string[];
    allowed_instance_types?: string[];
    networks?: ResourceNetwork[];
  };
}

export interface ResourceNetwork {
  source_id: number;
  region: string;
  vpc_id: string;
  subnet_id: string;
  zone: string;
  security_group_ids: string[];
}

export interface CreationCredential {
  id: number;
  source: number;
  name: string;
  revision: number;
  has_secret: boolean;
  is_active: boolean;
}

export interface ResourcePlan {
  id: number;
  status: string;
  digest: string;
  summary: { address: string; type: string; action: string }[];
  error_message: string;
  expires_at: string;
  confirmed_by: number | null;
  resource_snapshot?: Record<string, unknown>;
  attempt?: { id: number; status: string; error_message: string; instance_ids: string[]; asset_ids: number[] } | null;
}

export interface ResourceParameters {
  count: number;
  name: string;
  image_id: string;
  instance_type: string;
  zone: string;
  vpc_id: string;
  subnet_id: string;
  security_group_ids: string[];
  system_disk_gb: number;
}

export interface ResourceApplication {
  id: number;
  name: string;
  created_by: number;
  version: number;
  credential: number;
  region: string;
  parameters: ResourceParameters;
  approval_status: string;
  execution_status: string;
  inventory_status: string;
  source_name: string;
  template_name: string;
  plans: ResourcePlan[];
  allowed_actions: string[];
  created_at: string;
  stateProtection: { status: string; versionId: number | null; verifiedAt: string | null; message: string };
}

export interface StateVersion {
  id: number;
  version: number;
  serial: number;
  status: string;
  createdAt: string;
  verifiedAt: string | null;
  message: string;
}

export interface RestorePreview {
  previewId: string;
  digest: string;
  expiresAt: string;
  stateVersionId: number;
  serial: number;
  notice: string;
  instanceIds: string[];
  version: number;
  createdAt: string;
  status: string;
}

export interface ResolutionObservedAsset {
  instanceId: string;
  hostname?: string;
  internal_ip?: string;
  external_ip?: string | null;
  os_family?: string;
  cloud_state?: string;
  region?: string;
}

export interface ResolutionPreview {
  previewId: string;
  digest: string;
  expiresAt: string;
  stateVersionId: number;
  stateDigest: string;
  serial: number;
  instanceIds: string[];
  observedAssets: ResolutionObservedAsset[];
  notice: string;
}

export interface ResolutionConfirmation {
  previewId: string;
  digest: string;
  evidenceReference: string;
  comment: string;
}

export interface ProvisioningHealth {
  workers: { id: string; online: boolean; lastSeenAt: string; checks: Record<string, boolean> }[];
  queued: number;
  uncertain: number;
  incidents: { id: number; kind: string; message: string; created_at: string }[];
  observedAt: string;
  storage: { ready: boolean; message: string };
  retention: {
    planDays: number;
    diagnosticDays: number;
    retiredStateDays: number;
    auditDays: number;
    activeStateProtected: boolean;
  };
}

export interface ResourceEvent {
  id: number;
  kind: string;
  message: string;
  created_at: string;
}

interface Page<T> {
  list: T[];
  total: number;
}

const base = '/api/v1/provisioning';

export type CatalogKind =
  | 'zones'
  | 'images'
  | 'instance_types'
  | 'vpcs'
  | 'subnets'
  | 'security_groups'
  | 'availability'
  | 'quota';

export interface CloudCatalogItem {
  id: string;
  name: string;
  description: string;
  available: boolean | null;
  unavailableReason: string;
  attributes: {
    cpu?: number | null;
    memoryMiB?: number | null;
    architecture?: string | null;
    os?: string | null;
    family?: string | null;
    source?: string | null;
    zone?: string | null;
    vpcId?: string | null;
    cidr?: string | null;
    remaining?: number | null;
    unit?: string;
  };
}

export interface CloudCatalogQuery {
  kind: CatalogKind;
  versionId: number;
  credentialId?: number;
  sourceId?: number;
  region: string;
  zone?: string;
  vpcId?: string;
  instanceType?: string;
  imageId?: string;
  resourceId?: string;
  search?: string;
  cursor?: string;
  pageSize?: number;
  refresh?: boolean;
}

export interface CloudCatalogPage {
  items: CloudCatalogItem[];
  hasMore: boolean;
  nextCursor: string | null;
  observedAt: string;
  warnings: string[];
}

export function fetchCloudCatalog(params: CloudCatalogQuery) {
  return request<CloudCatalogPage>({ url: `${base}/catalog`, params });
}

export function fetchCloudConfigurationCatalog(params: CloudCatalogQuery) {
  return request<CloudCatalogPage>({ url: `${base}/catalog/configuration`, params });
}

export function fetchStateVersions(id: number) {
  return request<StateVersion[]>({ url: `${base}/requests/${id}/state-versions` });
}

export function previewStateRestore(id: number, stateVersionId: number) {
  return request<RestorePreview>({
    url: `${base}/requests/${id}/restore-preview`,
    method: 'post',
    data: { stateVersionId }
  });
}

export function confirmStateRestore(id: number, preview: RestorePreview) {
  return request<{ stateVersionId: number; status: string }>({
    url: `${base}/requests/${id}/restore-confirm`,
    method: 'post',
    data: { previewId: preview.previewId, digest: preview.digest }
  });
}

export function previewResourceResolution(id: number, stateVersionId?: number) {
  return request<ResolutionPreview>({
    url: `${base}/requests/${id}/resolution-preview`,
    method: 'post',
    data: stateVersionId === undefined ? {} : { stateVersionId }
  });
}

export function confirmResourceResolution(id: number, data: ResolutionConfirmation) {
  return request<{ execution_status: 'success'; inventory_status: 'success'; stateVersionId: number }>({
    url: `${base}/requests/${id}/resolution-confirm`,
    method: 'post',
    data
  });
}

export function fetchProvisioningHealth() {
  return request<ProvisioningHealth>({ url: `${base}/operations/health` });
}

export function fetchResourceApplications(page: number, search: string) {
  return request<Page<ResourceApplication>>({
    url: `${base}/requests`,
    params: { pageNum: page, pageSize: 10, search }
  });
}

export function fetchResourceApplication(id: number) {
  return request<ResourceApplication>({ url: `${base}/requests/${id}` });
}

export function fetchResourceTemplates() {
  return request<ResourceTemplate[]>({ url: `${base}/templates` });
}

export function fetchResourceVersions() {
  return request<ResourceVersion[]>({ url: `${base}/versions` });
}

export function fetchCreationCredentials() {
  return request<CreationCredential[]>({ url: `${base}/credentials` });
}

export function createResourceApplication(
  data: Pick<ResourceApplication, 'name' | 'version' | 'credential' | 'region' | 'parameters'> & {
    notification_config?: { templateId: number };
  }
) {
  return request<ResourceApplication>({ url: `${base}/requests`, method: 'post', data });
}

export function resourceAction(
  id: number,
  action: 'plan' | 'confirm' | 'approve' | 'reject' | 'execute' | 'reconcile',
  options: { plan?: ResourcePlan; key?: string } = {}
) {
  return request<unknown>({
    url: `${base}/requests/${id}/${action}`,
    method: 'post',
    data: { plan_id: options.plan?.id, digest: options.plan?.digest, idempotency_key: options.key }
  });
}

export function fetchResourceEvents(id: number) {
  return request<ResourceEvent[]>({ url: `${base}/requests/${id}/events` });
}

export function createResourceTemplate(data: Omit<ResourceTemplate, 'id'>) {
  return request<ResourceTemplate>({ url: `${base}/templates`, method: 'post', data });
}

export function createResourceVersion(data: Pick<ResourceVersion, 'template' | 'number' | 'constraints'>) {
  return request<ResourceVersion>({ url: `${base}/versions`, method: 'post', data });
}

export function publishResourceVersion(id: number) {
  return request<ResourceVersion>({ url: `${base}/versions/${id}/publish`, method: 'post' });
}

export function saveCreationCredential(
  data: { name: string; source: number; secret?: Record<string, string>; is_active: boolean },
  id?: number
) {
  return request<CreationCredential>({
    url: `${base}/credentials${id ? `/${id}` : ''}`,
    method: id ? 'patch' : 'post',
    data
  });
}
