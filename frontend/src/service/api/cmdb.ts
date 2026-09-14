import { request } from '../request';

/**
 * 资产管理域 API（cmdb）。
 *
 * - 主机：GET/POST/PUT/DELETE /api/v1/cmdb/hosts（读 camelCase / 写 snake_case）+ bulk-import/excel-import/relations
 * - 分组、标签、业务、服务树、资产来源：fields="__all__" 输出 snake_case（serializer 附加驼峰字段）
 * - 同步记录只读；资产来源 sync action 触发异步同步任务
 */

/** 后端分页响应（common.pagination） */
interface BackendPaginated<T> {
  list: T[];
  total: number;
  page: number;
  size: number;
}

type QueryValue = string | number | boolean | undefined | null;

/** 分页 + search + 附加筛选 → 后端 query（snake_case） */
function toPageQuery(
  params?: { current: number; size: number; search?: string | null },
  extra?: Record<string, QueryValue>
) {
  const query: Record<string, string | number | boolean> = {};
  if (params?.current) query.pageNum = params.current;
  if (params?.size) query.pageSize = params.size;
  if (params?.search) query.search = params.search;
  for (const [key, value] of Object.entries(extra ?? {})) {
    if (value !== undefined && value !== null && value !== '') query[key] = value;
  }
  return query;
}

/** 统一将 BackendPaginated 转换为前端分页结构 */
async function fetchPaginated<T>(url: string, query: Record<string, string | number | boolean>) {
  const res = await request<BackendPaginated<T>>({ url, method: 'get', params: query });

  if (res.error) return res;
  return {
    ...res,
    data: { records: res.data.list, current: res.data.page, size: res.data.size, total: res.data.total }
  };
}

/** 通用资源 CRUD（fields="__all__" snake_case 序列化器） */
function createCrudApi<TRecord, TPayload>(basePath: string) {
  return {
    fetchGetList: (params?: { current: number; size: number; search?: string | null } & Record<string, QueryValue>) => {
      const { current, size, search, ...extra } = params ?? { current: 1, size: 10 };
      return fetchPaginated<TRecord>(basePath, toPageQuery({ current, size, search }, extra));
    },
    fetchAdd: (data: TPayload) => request<TRecord>({ url: basePath, method: 'post', data }),
    fetchUpdate: (id: number, data: Partial<TPayload>) =>
      request<TRecord>({ url: `${basePath}/${id}`, method: 'put', data }),
    fetchDelete: (id: number) => request<null>({ url: `${basePath}/${id}`, method: 'delete' })
  };
}

/** 通用资源列表（孤儿调试视图使用，pageSize=100） */
export async function fetchGetCmdbResourceList(path: string) {
  return request<{ list: Array<Record<string, unknown>>; total: number; page: number; size: number }>({
    url: `/api/v1/cmdb/${path}`,
    method: 'get',
    params: { pageNum: 1, pageSize: 100 }
  });
}

/** ==================== 主机 ==================== */

export function fetchGetHostList(params?: Api.Cmdb.HostSearchParams) {
  return fetchPaginated<Api.Cmdb.HostRecord>(
    '/api/v1/cmdb/hosts',
    toPageQuery(params, {
      os_family: params?.osFamily,
      status: params?.status,
      environment: params?.environment,
      business: params?.business,
      service_node__in: params?.serviceNodeIds?.join(',')
    })
  );
}

/** 新增主机 */
export function fetchAddHost(data: Api.Cmdb.HostPayload) {
  return request<Api.Cmdb.HostRecord>({ url: '/api/v1/cmdb/hosts', method: 'post', data });
}

/** 更新主机 */
export function fetchUpdateHost(id: number, data: Partial<Api.Cmdb.HostPayload>) {
  return request<Api.Cmdb.HostRecord>({ url: `/api/v1/cmdb/hosts/${id}`, method: 'put', data });
}

/** 局部更新主机（PATCH，用于移动主机到服务树节点等轻量操作） */
export function fetchPatchHost(id: number, data: Partial<Api.Cmdb.HostPayload>) {
  return request<Api.Cmdb.HostRecord>({ url: `/api/v1/cmdb/hosts/${id}`, method: 'patch', data });
}

/** 删除主机 */
export function fetchDeleteHost(id: number) {
  return request<null>({ url: `/api/v1/cmdb/hosts/${id}`, method: 'delete' });
}

/** 主机 Excel 导入（POST hosts/excel-import，multipart 上传 .xlsx） */
export function fetchExcelImportHosts(file: File, groupIds?: string[]) {
  const form = new FormData();
  form.append('file', file);
  if (groupIds?.length) form.append('group_ids', groupIds.join(','));
  return request<Api.Cmdb.HostImportSummary>({
    url: '/api/v1/cmdb/hosts/excel-import',
    method: 'post',
    data: form
  });
}

/** 主机分组/标签关系（GET hosts/{id}/relations） */
export function fetchGetHostRelations(id: number) {
  return request<Api.Cmdb.HostRelations>({ url: `/api/v1/cmdb/hosts/${id}/relations`, method: 'get' });
}

/** 更新主机分组/标签关系（POST hosts/{id}/relations，全量覆盖） */
export function fetchUpdateHostRelations(id: number, data: Api.Cmdb.HostRelations) {
  return request<Api.Cmdb.HostRelations>({ url: `/api/v1/cmdb/hosts/${id}/relations`, method: 'post', data });
}

/** ==================== 主机分组 ==================== */

const hostGroupApi = createCrudApi<Api.Cmdb.HostGroupRecord, Api.Cmdb.HostGroupPayload>('/api/v1/cmdb/host-groups');

export function fetchGetHostGroupList(params?: Api.Cmdb.HostGroupSearchParams) {
  return hostGroupApi.fetchGetList({
    current: params?.current ?? 1,
    size: params?.size ?? 10,
    search: params?.search,
    group_type: params?.groupType,
    is_active: params?.isActive
  });
}

export function fetchAddHostGroup(data: Api.Cmdb.HostGroupPayload) {
  return hostGroupApi.fetchAdd(data);
}

export function fetchUpdateHostGroup(id: number, data: Partial<Api.Cmdb.HostGroupPayload>) {
  return hostGroupApi.fetchUpdate(id, data);
}

export function fetchDeleteHostGroup(id: number) {
  return hostGroupApi.fetchDelete(id);
}

/** 分组成员（GET host-groups/{id}/members，返回 string 主机 ID） */
export function fetchGetHostGroupMembers(id: number) {
  return request<{ hostIds: string[] }>({ url: `/api/v1/cmdb/host-groups/${id}/members`, method: 'get' });
}

/** 更新分组成员（POST host-groups/{id}/members，全量覆盖；动态分组后端拒绝） */
export function fetchUpdateHostGroupMembers(id: number, hostIds: string[]) {
  return request<null>({ url: `/api/v1/cmdb/host-groups/${id}/members`, method: 'post', data: { hostIds } });
}

/** ==================== 主机标签 ==================== */

const tagApi = createCrudApi<Api.Cmdb.HostTagRecord, Api.Cmdb.HostTagPayload>('/api/v1/cmdb/tags');

export function fetchGetTagList(params?: Api.Cmdb.HostTagSearchParams) {
  return tagApi.fetchGetList({
    current: params?.current ?? 1,
    size: params?.size ?? 10,
    search: params?.search,
    key: params?.key,
    value: params?.value
  });
}

export function fetchAddTag(data: Api.Cmdb.HostTagPayload) {
  return tagApi.fetchAdd(data);
}

export function fetchUpdateTag(id: number, data: Partial<Api.Cmdb.HostTagPayload>) {
  return tagApi.fetchUpdate(id, data);
}

export function fetchDeleteTag(id: number) {
  return tagApi.fetchDelete(id);
}

/** ==================== 业务系统 ==================== */

const businessApi = createCrudApi<Api.Cmdb.BusinessRecord, Api.Cmdb.BusinessPayload>('/api/v1/cmdb/businesses');

export function fetchGetBusinessList(params?: Api.Cmdb.BusinessSearchParams) {
  return businessApi.fetchGetList({
    current: params?.current ?? 1,
    size: params?.size ?? 10,
    search: params?.search,
    code: params?.code,
    is_active: params?.isActive
  });
}

export function fetchAddBusiness(data: Api.Cmdb.BusinessPayload) {
  return businessApi.fetchAdd(data);
}

export function fetchUpdateBusiness(id: number, data: Partial<Api.Cmdb.BusinessPayload>) {
  return businessApi.fetchUpdate(id, data);
}

export function fetchDeleteBusiness(id: number) {
  return businessApi.fetchDelete(id);
}

/** ==================== 服务树节点 ==================== */

const serviceNodeApi = createCrudApi<Api.Cmdb.ServiceTreeNodeRecord, Api.Cmdb.ServiceTreeNodePayload>(
  '/api/v1/cmdb/service-tree-nodes'
);

export function fetchGetServiceNodeList(params?: Api.Cmdb.ServiceTreeNodeSearchParams) {
  return serviceNodeApi.fetchGetList({
    current: params?.current ?? 1,
    size: params?.size ?? 10,
    search: params?.search,
    business: params?.business,
    node_type: params?.nodeType,
    is_active: params?.isActive
  });
}

export function fetchAddServiceNode(data: Api.Cmdb.ServiceTreeNodePayload) {
  return serviceNodeApi.fetchAdd(data);
}

export function fetchUpdateServiceNode(id: number, data: Partial<Api.Cmdb.ServiceTreeNodePayload>) {
  return serviceNodeApi.fetchUpdate(id, data);
}

export function fetchDeleteServiceNode(id: number) {
  return serviceNodeApi.fetchDelete(id);
}

/** ==================== 资产来源 ==================== */

const assetSourceApi = createCrudApi<Api.Cmdb.AssetSourceRecord, Api.Cmdb.AssetSourcePayload>(
  '/api/v1/cmdb/asset-sources'
);

export function fetchGetAssetSourceList(params?: Api.Cmdb.AssetSourceSearchParams) {
  return assetSourceApi.fetchGetList({
    current: params?.current ?? 1,
    size: params?.size ?? 10,
    search: params?.search,
    source_type: params?.sourceType,
    is_active: params?.isActive
  });
}

export function fetchAddAssetSource(data: Api.Cmdb.AssetSourcePayload) {
  return assetSourceApi.fetchAdd(data);
}

export function fetchUpdateAssetSource(id: number, data: Partial<Api.Cmdb.AssetSourcePayload>) {
  return assetSourceApi.fetchUpdate(id, data);
}

export function fetchDeleteAssetSource(id: number) {
  return assetSourceApi.fetchDelete(id);
}

/** 触发资产来源同步（POST asset-sources/{id}/sync，assets 为 JSON 数组，异步任务执行） */
export function fetchSyncAssetSource(id: number, assets: Array<Record<string, unknown>>) {
  return request<Api.Cmdb.AssetSyncRecordRecord>({
    url: `/api/v1/cmdb/asset-sources/${id}/sync`,
    method: 'post',
    data: { assets }
  });
}

/** ==================== 资产同步记录（只读） ==================== */

export function fetchGetSyncRecordList(params?: Api.Cmdb.AssetSyncRecordSearchParams) {
  return fetchPaginated<Api.Cmdb.AssetSyncRecordRecord>(
    '/api/v1/cmdb/asset-sync-records',
    toPageQuery(params, {
      source: params?.source,
      status: params?.status
    })
  );
}

/** ==================== 凭据引用 ==================== */

export function fetchGetCredentialRefList(params?: Api.Cmdb.CredentialRefSearchParams) {
  return fetchPaginated<Api.Cmdb.CredentialRefRecord>(
    '/api/v1/cmdb/credential-refs',
    toPageQuery(params, {
      type: params?.type,
      scope: params?.scope,
      is_active: params?.isActive
    })
  );
}

/** 新增凭据引用 */
export function fetchAddCredentialRef(data: Api.Cmdb.CredentialRefPayload) {
  return request<Api.Cmdb.CredentialRefRecord>({
    url: '/api/v1/cmdb/credential-refs',
    method: 'post',
    data
  });
}

/** 更新凭据引用 */
export function fetchUpdateCredentialRef(id: number, data: Partial<Api.Cmdb.CredentialRefPayload>) {
  return request<Api.Cmdb.CredentialRefRecord>({
    url: `/api/v1/cmdb/credential-refs/${id}`,
    method: 'put',
    data
  });
}

/** 删除凭据引用 */
export function fetchDeleteCredentialRef(id: number) {
  return request<null>({
    url: `/api/v1/cmdb/credential-refs/${id}`,
    method: 'delete'
  });
}

/** 凭据连接测试（POST credential-refs/{id}/test-connection） */
export function fetchTestCredentialConnection(id: number) {
  return request<Record<string, unknown>>({
    url: `/api/v1/cmdb/credential-refs/${id}/test-connection`,
    method: 'post'
  });
}
