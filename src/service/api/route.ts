import { request } from '../request';

/**
 * get user routes
 *
 * 对接后端动态路由接口：GET /api/v1/menus/routes，
 * 后端直接输出 soybean 约定的 UserRoute 结构（{ routes, home }）。
 */
export function fetchGetUserRoutes() {
  return request<Api.Route.UserRoute>({ url: '/api/v1/menus/routes' });
}
