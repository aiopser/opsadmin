import { request } from '../request';

/**
 * 知识库域 API（wiki）。
 *
 * - 目录树：GET /api/v1/wiki/pages/tree（返回扁平节点列表，由前端组装成树）
 * - 文档：GET/POST/PUT/DELETE /api/v1/wiki/pages（serializer 输出 snake_case）
 * - 图片：POST /api/v1/files（multipart，common/api/file_views.py）
 */

/** 获取知识库目录树（扁平列表，含 parent 字段） */
export function fetchGetWikiTree() {
  return request<Api.Wiki.PageNode[]>({ url: '/api/v1/wiki/pages/tree', method: 'get' });
}

/** 获取文档详情（含 Markdown 正文） */
export function fetchGetWikiPage(id: number) {
  return request<Api.Wiki.PageDetail>({ url: `/api/v1/wiki/pages/${id}`, method: 'get' });
}

/** 新建节点（目录或文档） */
export function fetchCreateWikiPage(data: Api.Wiki.PagePayload) {
  return request<Api.Wiki.PageDetail>({ url: '/api/v1/wiki/pages', method: 'post', data });
}

/** 更新节点（标题 / 正文 / 父节点 / 排序） */
export function fetchUpdateWikiPage(id: number, data: Api.Wiki.PagePayload) {
  return request<Api.Wiki.PageDetail>({ url: `/api/v1/wiki/pages/${id}`, method: 'put', data });
}

/** 删除节点（CASCADE 连带删除全部子节点） */
export function fetchDeleteWikiPage(id: number) {
  return request<null>({ url: `/api/v1/wiki/pages/${id}`, method: 'delete' });
}

/**
 * 上传 Markdown 正文中的图片（multipart）。
 *
 * 后端返回的是 `/media/xxx` 相对路径，页面回显需拼上后端服务地址，
 * 否则会被解析到前端域名下导致 404。
 */
export async function fetchUploadWikiFile(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await request<Api.Wiki.UploadedFile>({ url: '/api/v1/files', method: 'post', data: form });
  if (res.error || !res.data) return res;
  return { ...res, data: { ...res.data, url: resolveBackendUrl(res.data.url) } };
}

/** 相对路径拼后端 origin（VITE_SERVICE_BASE_URL 只配 origin，不带路径） */
function resolveBackendUrl(url: string) {
  if (!url.startsWith('/')) return url;
  const origin = import.meta.env.VITE_SERVICE_BASE_URL.replace(/\/+$/, '');
  return origin.startsWith('http') ? `${origin}${url}` : url;
}
