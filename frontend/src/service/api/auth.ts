import type { FlatResponseData } from '@sa/axios';
import { request } from '../request';

/** 后端登录响应（LoginApiView / MyTokenSerializer） */
interface BackendLoginToken {
  access: string;
  refresh: string;
  expire?: number;
  username?: string;
  email?: string;
}

/** 后端刷新令牌响应（RefreshTokenApiView） */
interface BackendRefreshToken {
  accessToken: string;
  refreshToken: string;
  tokenType?: string;
  expiresIn?: number;
}

/** 后端当前用户信息（UserProfileSerializer to_representation） */
interface BackendUserInfo {
  userId?: string;
  id?: number;
  username?: string;
  nickname?: string;
  roles?: string[];
  perms?: string[];
  email?: string | null;
  mobile?: string | null;
  deptName?: string | null;
  avatar?: string | null;
  createTime?: string | null;
}

/** 映射 flat 响应中的 data（与 system-manage.ts 的 mapFlatResponse 同模式） */
function mapData<T, R>(res: FlatResponseData<any, T>, mapper: (data: T) => R): FlatResponseData<any, R> {
  if (res.error || res.data === null) {
    return { data: null, error: res.error, response: res.response } as FlatResponseData<any, R>;
  }

  return { data: mapper(res.data), error: null, response: res.response };
}

/**
 * Login
 *
 * 后端 POST /api/v1/auth/login（请求字段 username），
 * 响应 data: { access, refresh, expire, ... } 映射为前端 token 结构
 *
 * @param userName User name
 * @param password Password
 */
export async function fetchLogin(userName: string, password: string) {
  const res = await request<BackendLoginToken>({
    url: '/api/v1/auth/login',
    method: 'post',
    data: {
      username: userName,
      password
    }
  });

  return mapData(res, data => ({
    token: data.access,
    refreshToken: data.refresh
  }));
}

/**
 * Get user info
 *
 * 后端 GET /api/v1/auth/me（UserProfileSerializer），
 * roles 为角色名列表、perms 为按钮/接口权限码列表
 */
export async function fetchGetUserInfo() {
  const res = await request<BackendUserInfo>({ url: '/api/v1/auth/me' });

  return mapData(res, data => ({
    userId: data.userId ?? (data.id !== undefined ? String(data.id) : ''),
    userName: data.username ?? '',
    roles: data.roles ?? [],
    buttons: data.perms ?? []
  }));
}

/** 个人中心：获取后端原始用户信息（GET /api/v1/auth/me，不做字段裁剪） */
export async function fetchGetUserProfile() {
  const res = await request<BackendUserInfo>({
    url: '/api/v1/auth/me',
    method: 'get'
  });

  return mapData(res, data => ({
    userId: data.userId ?? (data.id !== undefined ? String(data.id) : ''),
    username: data.username ?? '',
    nickname: data.nickname ?? '',
    roles: data.roles ?? [],
    perms: data.perms ?? [],
    email: data.email ?? '',
    mobile: data.mobile ?? '',
    deptName: data.deptName ?? '',
    avatar: data.avatar ?? '',
    createTime: data.createTime ?? ''
  }));
}

/**
 * 个人中心：更新当前用户资料（PUT /api/v1/users/profile）
 *
 * 传入 FormData 时支持 avatar 字段直接上传头像文件（multipart），
 * 传入普通对象时可更新 nickname / email / mobile 等字段
 */
export async function fetchUpdateUserProfile(data: FormData | Record<string, unknown>) {
  return request<BackendUserInfo>({
    url: '/api/v1/users/profile',
    method: 'put',
    data
  });
}

/**
 * 个人中心：修改当前用户密码（PUT /api/v1/users/password）
 *
 * 后端校验原密码，成功后返回提示文案
 */
export async function fetchUpdateUserPassword(oldPassword: string, newPassword: string) {
  return request<string>({
    url: '/api/v1/users/password',
    method: 'put',
    data: { oldPassword, newPassword }
  });
}

/**
 * Refresh token
 *
 * 后端 POST /api/v1/auth/refresh-token，
 * 响应 data: { accessToken, refreshToken, ... } 映射为前端 token 结构
 *
 * @param refreshToken Refresh token
 */
export async function fetchRefreshToken(refreshToken: string) {
  const res = await request<BackendRefreshToken>({
    url: '/api/v1/auth/refresh-token',
    method: 'post',
    data: {
      refreshToken
    }
  });

  return mapData(res, data => ({
    token: data.accessToken,
    refreshToken: data.refreshToken
  }));
}

/**
 * return custom backend error
 *
 * @param code error code
 * @param msg error message
 */
export function fetchCustomBackendError(code: string, msg: string) {
  return request({ url: '/auth/error', params: { code, msg } });
}
