import type { FlatResponseData } from '@sa/axios';
import { request } from '../request';

/**
 * ============ 后端原始数据结构 ============
 *
 * 与后端 Django REST 接口（/api/v1/*）返回的字段一一对应。
 * 前端通过下方的 transform 函数将其转换为 Api.SystemManage 类型。
 */

/** 后端分页响应（common.pagination.StandardResultSetPagination） */
interface BackendPaginated<T> {
  list?: T[];
  result?: T[];
  total?: number;
  count?: number;
  page?: number;
  size?: number;
  num_pages?: number;
}

/** 后端用户记录（UserProfileSerializer 输出） */
interface BackendUser {
  id: number;
  username?: string;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  gender?: number | null;
  is_active?: boolean;
  is_superuser?: boolean;
  status?: number;
  role_codes?: string[];
  created_at?: string;
  updated_at?: string;
  date_joined?: string;
  createTime?: string;
  updateTime?: string;
}

/** 后端角色记录（RoleSerializer 输出） */
interface BackendRole {
  id: number;
  name?: string;
  code?: string | null;
  description?: string;
  is_active?: boolean;
  is_system?: boolean;
  home_path?: string | null;
  roleName?: string;
  roleCode?: string;
  roleDesc?: string;
  status?: Api.Common.EnableStatus;
  created_at?: string;
  updated_at?: string;
}

/** 后端菜单记录（MenuSerializer 输出） */
interface BackendMenu {
  id: number;
  title?: string;
  name?: string;
  path?: string;
  component?: string | null;
  icon?: string | null;
  icon_type?: string;
  iconType?: string;
  i18n_key?: App.I18n.I18nKey | null;
  i18nKey?: App.I18n.I18nKey | null;
  href?: string | null;
  multi_tab?: boolean;
  multiTab?: boolean;
  fixed_index_in_tab?: number | null;
  fixedIndexInTab?: number | null;
  query?: Api.SystemManage.Menu['query'];
  constant?: boolean;
  is_active?: boolean;
  active_menu?: string | null;
  type?: 'C' | 'M';
  menu_type?: string;
  pid?: number | null;
  parentId?: string;
  routeName?: string;
  routePath?: string;
  order?: number;
  sort?: number;
  status?: string;
  hideInMenu?: boolean;
  keepAlive?: boolean;
  buttons?: Api.SystemManage.MenuButton[] | null;
  children?: BackendMenu[] | null;
  created_at?: string;
  updated_at?: string;
}

/** 后端菜单树节点（menus/tree 接口输出，MenuSerializer + children） */
interface BackendMenuTreeNode {
  id: number;
  title?: string;
  name?: string;
  pid?: number | null;
  parentId?: string;
  children?: BackendMenuTreeNode[];
}

/** 后端部门记录（DepartmentSerializer 输出） */
interface BackendDepartment {
  id: number;
  name?: string;
  code?: string | null;
  parent?: number | null;
  parentId?: string;
  sort?: number;
  status?: number | string;
  treePath?: string;
  createTime?: string;
  updateTime?: string;
  created_at?: string;
  updated_at?: string;
  children?: BackendDepartment[];
}

/** ============ 转换工具 ============ */

/**
 * 将 request 的扁平响应中的 data 做映射转换，
 * 保持 { data, error, response } 结构不变，供 useUIPaginatedTable 消费。
 */
function mapFlatResponse<T, R>(res: FlatResponseData<any, T>, mapper: (data: T) => R): FlatResponseData<any, R> {
  if (res.error || res.data === null) {
    return { data: null, error: res.error, response: res.response } as FlatResponseData<any, R>;
  }

  return { data: mapper(res.data), error: null, response: res.response };
}

/** 提取后端列表数据（兼容分页结构与全量数组） */
function extractList<T>(raw: BackendPaginated<T> | T[]): T[] {
  if (Array.isArray(raw)) return raw;
  return raw.result ?? raw.list ?? [];
}

/** 后端分页结构/全量数组 → 前端 PaginatingQueryRecord */
function transformPaginated<T, R>(
  raw: BackendPaginated<T> | T[],
  mapItem: (item: T) => R
): Api.Common.PaginatingQueryRecord<R> {
  const records = extractList(raw).map(mapItem);
  const meta: BackendPaginated<T> = Array.isArray(raw) ? {} : raw;

  return {
    records,
    current: meta.page ?? 1,
    size: meta.size ?? records.length,
    total: meta.total ?? meta.count ?? records.length
  };
}

/** 后端性别数值 → 前端 UserGender */
function toUserGender(raw: BackendUser['gender']): Api.SystemManage.UserGender | undefined {
  if (raw === 1) return '1';
  if (raw === 2) return '2';
  return undefined;
}

/** 后端父级 ID（pid 数值 / parentId 字符串）→ 数值 */
function toParentId(raw: { pid?: number | null; parentId?: string | null }): number {
  if (raw.pid !== null && raw.pid !== undefined) {
    return raw.pid;
  }
  if (raw.parentId !== null && raw.parentId !== undefined) {
    return Number(raw.parentId);
  }
  return 0;
}

/** 后端菜单类型（C=目录 / M=菜单）→ 前端 MenuType（1=目录 / 2=菜单） */
function toMenuType(raw: Pick<BackendMenu, 'type' | 'menu_type'>): Api.SystemManage.MenuType {
  return (raw.type ?? raw.menu_type) === 'C' ? '1' : '2';
}

/** 菜单路由/展示元信息字段（拆分以控制 transformMenu 复杂度） */
function toMenuRouteMeta(raw: BackendMenu) {
  return {
    routeName: raw.routeName ?? raw.name ?? '',
    routePath: raw.routePath ?? raw.path ?? '',
    component: raw.component ?? '',
    keepAlive: raw.keepAlive ?? false,
    constant: raw.constant ?? false,
    href: raw.href ?? null,
    hideInMenu: raw.hideInMenu ?? false,
    activeMenu: (raw.active_menu as Api.SystemManage.Menu['activeMenu']) ?? undefined,
    multiTab: raw.multiTab ?? raw.multi_tab ?? false,
    fixedIndexInTab: raw.fixedIndexInTab ?? raw.fixed_index_in_tab ?? undefined,
    query: raw.query ?? null
  };
}

/** 后端用户 → 前端 User */
function transformUser(raw: BackendUser): Api.SystemManage.User {
  return {
    id: raw.id,
    userName: raw.username ?? '',
    nickName: raw.nickname ?? raw.name ?? '',
    userGender: toUserGender(raw.gender),
    userPhone: raw.mobile ?? raw.phone ?? '',
    userEmail: raw.email ?? '',
    userRoles: raw.role_codes ?? [],
    status: raw.is_active ? '1' : '2',
    isSuperuser: Boolean(raw.is_superuser) || raw.username === 'admin',
    createBy: '',
    createTime: raw.createTime ?? raw.created_at ?? raw.date_joined ?? '',
    updateBy: '',
    updateTime: raw.updateTime ?? raw.updated_at ?? ''
  };
}

/** 后端角色 → 前端 Role */
function transformRole(raw: BackendRole): Api.SystemManage.Role {
  return {
    id: raw.id,
    roleName: raw.roleName ?? raw.name ?? '',
    roleCode: raw.roleCode ?? raw.code ?? '',
    roleDesc: raw.roleDesc ?? raw.description ?? '',
    status: raw.status ?? (raw.is_active ? '1' : '2'),
    isSystem: Boolean(raw.is_system) || raw.name === 'system_admin',
    createBy: '',
    createTime: raw.created_at ?? '',
    updateBy: '',
    updateTime: raw.updated_at ?? ''
  };
}

/** 后端角色 → 前端 AllRole（角色下拉选项） */
function transformAllRole(raw: BackendRole): Api.SystemManage.AllRole {
  return {
    id: raw.id,
    roleName: raw.roleName ?? raw.name ?? '',
    roleCode: raw.roleCode ?? raw.code ?? ''
  };
}

/** 后端菜单 → 前端 Menu */
function transformMenu(raw: BackendMenu): Api.SystemManage.Menu {
  const status: Api.Common.EnableStatus = (raw.status ?? (raw.is_active ? '1' : '2')) as Api.Common.EnableStatus;

  return {
    id: raw.id,
    parentId: toParentId(raw),
    menuType: toMenuType(raw),
    menuName: raw.title ?? '',
    icon: raw.icon ?? '',
    iconType: (raw.iconType ?? raw.icon_type ?? '1') as Api.SystemManage.IconType,
    buttons: raw.buttons ?? [],
    order: raw.order ?? raw.sort ?? 0,
    i18nKey: raw.i18nKey ?? raw.i18n_key ?? null,
    status,
    createBy: '',
    createTime: raw.created_at ?? '',
    updateBy: '',
    updateTime: raw.updated_at ?? '',
    ...toMenuRouteMeta(raw)
  };
}

/** 后端菜单树节点 → 前端 MenuTree */
function transformMenuTreeNode(raw: BackendMenuTreeNode): Api.SystemManage.MenuTree {
  return {
    id: raw.id,
    label: raw.title ?? raw.name ?? '',
    pId: toParentId(raw),
    children: (raw.children ?? []).map(transformMenuTreeNode)
  };
}

/** 后端部门状态 → 前端 EnableStatus（"1" 启用 / "2" 禁用） */
function toDeptStatus(raw: BackendDepartment['status']): Api.Common.EnableStatus {
  if (typeof raw === 'number') return raw === 1 ? '1' : '2';
  if (raw === '1' || raw === '2') return raw;
  return '1';
}

/** 后端部门 → 前端 Department */
function transformDepartment(raw: BackendDepartment): Api.SystemManage.Department {
  return {
    id: raw.id,
    parentId: toParentId(raw),
    deptName: raw.name ?? '',
    deptCode: raw.code ?? '',
    sort: raw.sort ?? 0,
    status: toDeptStatus(raw.status),
    createBy: '',
    createTime: raw.createTime ?? raw.created_at ?? '',
    updateBy: '',
    updateTime: raw.updateTime ?? raw.updated_at ?? '',
    children: (raw.children ?? []).map(transformDepartment)
  };
}

/** ============ 查询参数转换 ============ */

function toUserQuery(params?: Api.SystemManage.UserSearchParams) {
  const query: Record<string, string | number> = {};
  if (!params) return query;

  if (params.current) query.pageNum = params.current;
  if (params.size) query.pageSize = params.size;
  if (params.userName) query.username = params.userName;
  if (params.nickName) query.name = params.nickName;
  if (params.userPhone) query.phone = params.userPhone;
  if (params.userEmail) query.email = params.userEmail;
  if (params.userGender) query.gender = params.userGender;
  if (params.status) query.status = params.status;

  return query;
}

function toRoleQuery(params?: Api.SystemManage.RoleSearchParams) {
  const query: Record<string, string | number> = {};
  if (!params) return query;

  if (params.current) query.pageNum = params.current;
  if (params.size) query.pageSize = params.size;
  if (params.roleName) query.roleName = params.roleName;
  if (params.roleCode) query.roleCode = params.roleCode;
  if (params.status) query.status = params.status;

  return query;
}

/** 将前端 userRoles（角色编码）转换为后端 role 所需的角色 ID */
async function resolveRoleIds(codes?: string[]): Promise<number[]> {
  if (!codes || codes.length === 0) return [];

  const res = await request<BackendRole[] | BackendPaginated<BackendRole>>({
    url: '/api/v1/roles',
    method: 'get',
    params: { status: '1' }
  });
  if (res.error || res.data === null) return [];

  const codeToId = new Map(extractList(res.data).map(role => [role.roleCode ?? role.code, role.id]));

  return codes.map(code => codeToId.get(code)).filter((id): id is number => id !== undefined);
}

/** 前端 UserModel → 后端用户创建/更新 payload */
async function toBackendUserPayload(data: Api.SystemManage.UserModel) {
  return {
    username: data.userName,
    name: data.nickName,
    gender: data.userGender ? Number(data.userGender) : undefined,
    phone: data.userPhone,
    email: data.userEmail,
    roleIds: await resolveRoleIds(data.userRoles),
    status: data.status ? Number(data.status) : undefined
  };
}

/** 前端 RoleModel → 后端角色 payload（后端 RoleSerializer 已支持 camelCase 字段） */
function toBackendRolePayload(data: Api.SystemManage.RoleModel) {
  return {
    roleName: data.roleName,
    roleCode: data.roleCode,
    roleDesc: data.roleDesc,
    status: data.status
  };
}

/** 前端 MenuModel → 后端菜单 payload */
function toBackendMenuPayload(data: Api.SystemManage.MenuModel) {
  return {
    type: data.menuType === '1' ? 'C' : 'M',
    title: data.menuName,
    routeName: data.routeName,
    routePath: data.routePath,
    component: data.component,
    order: data.order,
    i18nKey: data.i18nKey,
    icon: data.icon,
    iconType: data.iconType,
    status: data.status,
    parentId: data.parentId,
    keepAlive: data.keepAlive,
    constant: data.constant,
    href: data.href,
    hideInMenu: data.hideInMenu,
    active_menu: data.activeMenu,
    multiTab: data.multiTab,
    fixedIndexInTab: data.fixedIndexInTab,
    query: data.query,
    buttons: data.buttons
  };
}

/** ============ 角色 ============ */

/** get role list */
export async function fetchGetRoleList(params?: Api.SystemManage.RoleSearchParams) {
  const res = await request<BackendPaginated<BackendRole>>({
    url: '/api/v1/roles',
    method: 'get',
    params: toRoleQuery(params)
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformRole));
}

/**
 * get all enabled roles
 *
 * 后端无独立全量接口，复用角色列表（status=1 过滤启用角色），
 * 返回 AllRole[]（含 id/roleName/roleCode），供用户/菜单表单的角色下拉使用。
 */
export async function fetchGetAllRoles() {
  const res = await request<BackendRole[] | BackendPaginated<BackendRole>>({
    url: '/api/v1/roles',
    method: 'get',
    params: { status: '1' }
  });

  return mapFlatResponse(res, data => extractList(data).map(transformAllRole));
}

/** add role */
export function addRole(data: Api.SystemManage.RoleModel) {
  return request<null>({
    url: '/api/v1/roles',
    method: 'post',
    data: toBackendRolePayload(data)
  });
}

/** update role */
export function updateRole(id: number, data: Api.SystemManage.RoleModel) {
  return request<null>({
    url: `/api/v1/roles/${id}`,
    method: 'put',
    data: toBackendRolePayload(data)
  });
}

/** delete role */
export function deleteRole(id: number) {
  return request<null>({
    url: `/api/v1/roles/${id}`,
    method: 'delete'
  });
}

/** batch delete role（后端逗号分隔路径批量删除） */
export function batchDeleteRole(ids: number[]) {
  return request<null>({
    url: `/api/v1/roles/${ids.join(',')}`,
    method: 'delete'
  });
}

/** 获取角色已分配的菜单/按钮 ID（回显） */
export function fetchGetRoleMenuIds(roleId: number) {
  return request<{ menuIds: string[]; buttonIds: string[]; homePath: string | null }>({
    url: `/api/v1/roles/${roleId}/menu-ids`,
    method: 'get'
  });
}

/** 分配角色菜单/按钮 + 默认首页 */
export function updateRoleMenus(
  roleId: number,
  data: { menuIds: Array<string | number>; buttonIds: Array<string | number>; homePath?: string }
) {
  return request<null>({
    url: `/api/v1/roles/${roleId}/menus`,
    method: 'put',
    data
  });
}

/** ============ 用户 ============ */

/** get user list */
export async function fetchGetUserList(params?: Api.SystemManage.UserSearchParams) {
  const res = await request<BackendPaginated<BackendUser>>({
    url: '/api/v1/users',
    method: 'get',
    params: toUserQuery(params)
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformUser));
}

/** add user */
export async function addUser(data: Api.SystemManage.UserModel) {
  return request<null>({
    url: '/api/v1/users',
    method: 'post',
    data: await toBackendUserPayload(data)
  });
}

/** update user */
export async function updateUser(id: number, data: Api.SystemManage.UserModel) {
  return request<null>({
    url: `/api/v1/users/${id}`,
    method: 'put',
    data: await toBackendUserPayload(data)
  });
}

/** delete user */
export function deleteUser(id: number) {
  return request<null>({
    url: `/api/v1/users/${id}`,
    method: 'delete'
  });
}

/** batch delete user（后端逗号分隔路径批量删除） */
export function batchDeleteUser(ids: number[]) {
  return request<null>({
    url: `/api/v1/users/${ids.join(',')}`,
    method: 'delete'
  });
}

/** ============ 菜单 ============ */

/** get menu list（后端无分页参数时返回全量数组） */
export async function fetchGetMenuList() {
  const res = await request<BackendPaginated<BackendMenu> | BackendMenu[]>({
    url: '/api/v1/menus',
    method: 'get'
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformMenu));
}

/** get all menus（含按钮定义，按钮授权弹窗构建菜单→按钮树使用） */
export async function fetchGetAllMenus() {
  const res = await request<BackendMenu[] | BackendPaginated<BackendMenu>>({
    url: '/api/v1/menus',
    method: 'get'
  });

  return mapFlatResponse(res, data => extractList(data).map(transformMenu));
}

/** get all pages（页面组件名列表） */
export async function fetchGetAllPages() {
  const res = await request<string[]>({
    url: '/api/v1/menus/pages',
    method: 'get'
  });

  return mapFlatResponse(res, data => data);
}

/** get menu tree（角色授权弹窗的菜单勾选树） */
export async function fetchGetMenuTree() {
  const res = await request<BackendMenuTreeNode[]>({
    url: '/api/v1/menus/tree',
    method: 'get'
  });

  return mapFlatResponse(res, data => (data ?? []).map(transformMenuTreeNode));
}

/** get menu table tree（菜单管理表格树，节点含完整菜单字段与 children 嵌套） */
export async function fetchGetMenuTableTree() {
  const res = await request<BackendMenu[]>({
    url: '/api/v1/menus/tree',
    method: 'get'
  });

  return mapFlatResponse(res, data => {
    const toNode = (raw: BackendMenu): Api.SystemManage.Menu => {
      const children = (raw.children ?? []).map(toNode);

      const node: Api.SystemManage.Menu = { ...transformMenu(raw), children: children.length ? children : null };

      return node;
    };

    return {
      records: (data ?? []).map(toNode),
      current: 1,
      size: (data ?? []).length,
      total: (data ?? []).length
    };
  });
}

/** add menu */
export function addMenu(data: Api.SystemManage.MenuModel) {
  return request<null>({
    url: '/api/v1/menus',
    method: 'post',
    data: toBackendMenuPayload(data)
  });
}

/** update menu */
export function updateMenu(id: number, data: Api.SystemManage.MenuModel) {
  return request<null>({
    url: `/api/v1/menus/${id}`,
    method: 'put',
    data: toBackendMenuPayload(data)
  });
}

/** delete menu */
export function deleteMenu(id: number) {
  return request<null>({
    url: `/api/v1/menus/${id}`,
    method: 'delete'
  });
}

/** ============ 部门 ============ */

function toDeptQuery(params?: Api.SystemManage.DepartmentSearchParams) {
  const query: Record<string, string> = {};
  if (!params) return query;

  if (params.deptName) query.keywords = params.deptName;
  if (params.status) query.status = params.status;

  return query;
}

/** 通用分页参数（pageNum/pageSize）+ 可选状态过滤 */
function toPagingParams(params?: { current?: number | null; size?: number | null; status?: string | null }) {
  const query: Record<string, string | number> = {};
  if (params?.current) query.pageNum = params.current;
  if (params?.size) query.pageSize = params.size;
  if (params?.status) query.status = params.status;

  return query;
}

function toDictQuery(params?: Api.SystemManage.DictTypeSearchParams) {
  const query = toPagingParams(params);
  if (params?.dictName) query.keywords = params.dictName;

  return query;
}

function toDictItemQuery(params?: Api.SystemManage.DictItemSearchParams) {
  const query = toPagingParams(params);
  if (params?.label) query.keywords = params.label;

  return query;
}

function toConfigQuery(params?: Api.SystemManage.SystemConfigSearchParams) {
  const query = toPagingParams(params);
  if (params?.configName) query.keywords = params.configName;

  return query;
}

function toBackendDeptPayload(data: Api.SystemManage.DepartmentModel) {
  return {
    name: data.deptName,
    code: data.deptCode,
    parentId: data.parentId || null,
    sort: data.sort ?? 0,
    status: data.status ?? '1'
  };
}

/** get department tree list（后端返回树形结构，不分页） */
export async function fetchGetDeptList(params?: Api.SystemManage.DepartmentSearchParams) {
  const res = await request<BackendDepartment[]>({
    url: '/api/v1/depts',
    method: 'get',
    params: toDeptQuery(params)
  });

  return mapFlatResponse(res, data => (data ?? []).map(transformDepartment));
}

/** 部门树选项（ElTreeSelect 的 data 结构） */
export type DeptTreeOption = {
  id: number;
  value: number;
  label: string;
  children?: DeptTreeOption[];
};

/** 上级部门下拉树选项（由部门列表树转换） */
export async function fetchGetDeptTree() {
  const res = await fetchGetDeptList();

  return mapFlatResponse(res, data =>
    data.map(function mapNode(node: Api.SystemManage.Department): DeptTreeOption {
      return {
        id: node.id,
        value: node.id,
        label: node.deptName,
        children: (node.children ?? []).map(mapNode)
      };
    })
  );
}

/** add department */
export function addDept(data: Api.SystemManage.DepartmentModel) {
  return request<null>({
    url: '/api/v1/depts',
    method: 'post',
    data: toBackendDeptPayload(data)
  });
}

/** update department */
export function updateDept(id: number, data: Api.SystemManage.DepartmentModel) {
  return request<null>({
    url: `/api/v1/depts/${id}`,
    method: 'put',
    data: toBackendDeptPayload(data)
  });
}

/** delete department */
export function deleteDept(id: number) {
  return request<null>({
    url: `/api/v1/depts/${id}`,
    method: 'delete'
  });
}

/** batch delete department（后端逗号分隔路径批量删除） */
export function batchDeleteDept(ids: number[]) {
  return request<null>({
    url: `/api/v1/depts/${ids.join(',')}`,
    method: 'delete'
  });
}

/** ============ 字典 ============ */

interface BackendDictType {
  id: number;
  name?: string;
  code?: string;
  remark?: string | null;
  status?: number | string;
  createTime?: string;
  updateTime?: string;
}

interface BackendDictItem {
  id: number;
  dictCode?: string;
  label?: string;
  value?: string;
  sort?: number;
  tagType?: string;
  status?: number | string;
  createTime?: string;
  updateTime?: string;
}

/** 后端记录通用字段 → 前端 CommonRecord 字段 */
function toCommonRecordFields(raw: { createTime?: string; updateTime?: string; status?: number | string }) {
  return {
    status: toDeptStatus(raw.status),
    createBy: '',
    createTime: raw.createTime ?? '',
    updateBy: '',
    updateTime: raw.updateTime ?? ''
  } as Pick<Api.SystemManage.DictType, 'status' | 'createBy' | 'createTime' | 'updateBy' | 'updateTime'>;
}

function transformDictType(raw: BackendDictType): Api.SystemManage.DictType {
  return {
    id: raw.id,
    dictName: raw.name ?? '',
    dictCode: raw.code ?? '',
    remark: raw.remark ?? null,
    ...toCommonRecordFields(raw)
  };
}

function transformDictItem(raw: BackendDictItem): Api.SystemManage.DictItem {
  return {
    id: raw.id,
    dictCode: raw.dictCode ?? '',
    label: raw.label ?? '',
    value: raw.value ?? '',
    sort: raw.sort ?? 0,
    tagType: raw.tagType ?? '',
    ...toCommonRecordFields(raw)
  };
}

/** get dict type list */
export async function fetchGetDictList(params?: Api.SystemManage.DictTypeSearchParams) {
  const res = await request<BackendPaginated<BackendDictType>>({
    url: '/api/v1/dicts',
    method: 'get',
    params: toDictQuery(params)
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformDictType));
}

function toBackendDictTypePayload(data: Api.SystemManage.DictTypeModel) {
  return {
    name: data.dictName,
    code: data.dictCode,
    remark: data.remark,
    status: data.status ?? '1'
  };
}

/** add dict type */
export function addDict(data: Api.SystemManage.DictTypeModel) {
  return request<null>({ url: '/api/v1/dicts', method: 'post', data: toBackendDictTypePayload(data) });
}

/** update dict type */
export function updateDict(id: number, data: Api.SystemManage.DictTypeModel) {
  return request<null>({ url: `/api/v1/dicts/${id}`, method: 'put', data: toBackendDictTypePayload(data) });
}

/** delete dict type */
export function deleteDict(id: number) {
  return request<null>({ url: `/api/v1/dicts/${id}`, method: 'delete' });
}

/** get dict item list by dict code */
export async function fetchGetDictItemList(dictCode: string, params?: Api.SystemManage.DictItemSearchParams) {
  // dictCode 为空时不发请求（弹窗组件常驻渲染，初始化阶段尚无选中字典），
  // 避免拼出 /api/v1/dicts//items 产生 404
  if (!dictCode) {
    return {
      data: { records: [], current: params?.current ?? 1, size: params?.size ?? 10, total: 0 },
      error: null,
      response: null
    } as unknown as FlatResponseData<any, Api.Common.PaginatingQueryRecord<Api.SystemManage.DictItem>>;
  }

  const res = await request<BackendPaginated<BackendDictItem>>({
    url: `/api/v1/dicts/${dictCode}/items`,
    method: 'get',
    params: toDictItemQuery(params)
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformDictItem));
}

function toBackendDictItemPayload(data: Api.SystemManage.DictItemModel) {
  return {
    label: data.label,
    value: data.value,
    sort: data.sort ?? 0,
    tagType: data.tagType ?? '',
    status: data.status ?? '1'
  };
}

/** add dict item */
export function addDictItem(dictCode: string, data: Api.SystemManage.DictItemModel) {
  return request<null>({
    url: `/api/v1/dicts/${dictCode}/items`,
    method: 'post',
    data: toBackendDictItemPayload(data)
  });
}

/** update dict item */
export function updateDictItem(dictCode: string, id: number, data: Api.SystemManage.DictItemModel) {
  return request<null>({
    url: `/api/v1/dicts/${dictCode}/items/${id}`,
    method: 'put',
    data: toBackendDictItemPayload(data)
  });
}

/** delete dict item */
export function deleteDictItem(dictCode: string, id: number) {
  return request<null>({
    url: `/api/v1/dicts/${dictCode}/items/${id}`,
    method: 'delete'
  });
}

/** ============ 系统配置 ============ */

interface BackendSystemConfig {
  id: number;
  configName?: string;
  configKey?: string;
  configValue?: string | null;
  configGroup?: string;
  remark?: string | null;
  status?: number | string;
  createTime?: string;
  updateTime?: string;
}

function transformSystemConfig(raw: BackendSystemConfig): Api.SystemManage.SystemConfig {
  return {
    id: raw.id,
    configName: raw.configName ?? '',
    configKey: raw.configKey ?? '',
    configValue: raw.configValue ?? null,
    configGroup: raw.configGroup ?? '',
    remark: raw.remark ?? null,
    ...toCommonRecordFields(raw)
  };
}

/** get system config list */
export async function fetchGetConfigList(params?: Api.SystemManage.SystemConfigSearchParams) {
  const res = await request<BackendPaginated<BackendSystemConfig>>({
    url: '/api/v1/configs',
    method: 'get',
    params: toConfigQuery(params)
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformSystemConfig));
}

function toBackendConfigPayload(data: Api.SystemManage.SystemConfigModel) {
  return {
    configName: data.configName,
    configKey: data.configKey,
    configValue: data.configValue ?? '',
    configGroup: data.configGroup ?? '',
    remark: data.remark,
    status: data.status ?? '1'
  };
}

/** add system config */
export function addConfig(data: Api.SystemManage.SystemConfigModel) {
  return request<null>({ url: '/api/v1/configs', method: 'post', data: toBackendConfigPayload(data) });
}

/** update system config */
export function updateConfig(id: number, data: Api.SystemManage.SystemConfigModel) {
  return request<null>({ url: `/api/v1/configs/${id}`, method: 'put', data: toBackendConfigPayload(data) });
}

/** delete system config */
export function deleteConfig(id: number) {
  return request<null>({ url: `/api/v1/configs/${id}`, method: 'delete' });
}

/** get public site configs（无需登录，仅返回白名单键） */
export async function fetchGetPublicConfigs() {
  const res = await request<Record<string, string>>({
    url: '/api/v1/configs/public',
    method: 'get'
  });

  return mapFlatResponse(res, data => data ?? {});
}

/** ============ 系统日志 ============ */

interface BackendOperationLog {
  id: number;
  module?: string;
  actionType?: string;
  title?: string;
  requestUri?: string;
  requestMethod?: string;
  operatorName?: string;
  ip?: string;
  status?: number;
  executionTime?: number;
  errorMsg?: string;
  createTime?: string;
}

function transformOperationLog(raw: BackendOperationLog): Api.SystemManage.OperationLog {
  return {
    id: raw.id,
    module: raw.module ?? '',
    actionType: raw.actionType ?? '',
    title: raw.title ?? '',
    requestUri: raw.requestUri ?? '',
    requestMethod: raw.requestMethod ?? '',
    operatorName: raw.operatorName ?? '',
    ip: raw.ip ?? '',
    status: toDeptStatus(raw.status),
    executionTime: raw.executionTime ?? 0,
    errorMsg: raw.errorMsg ?? '',
    createTime: raw.createTime ?? ''
  };
}

/** get operation log list（只读分页） */
export async function fetchGetLogList(params?: Api.SystemManage.OperationLogSearchParams) {
  const query = toPagingParams(params);

  if (params) {
    if (params.keywords) query.keywords = params.keywords;
    if (params.createTime?.length === 2) {
      query.startDate = params.createTime[0];
      query.endDate = params.createTime[1];
    }
  }

  const res = await request<BackendPaginated<BackendOperationLog>>({
    url: '/api/v1/logs',
    method: 'get',
    params: query
  });

  return mapFlatResponse(res, data => transformPaginated(data, transformOperationLog));
}

/** batch delete operation logs */
export function batchDeleteLogs(ids: number[]) {
  return request<{ deleted: number }>({
    url: `/api/v1/logs/delete/${ids.join(',')}`,
    method: 'delete'
  });
}
