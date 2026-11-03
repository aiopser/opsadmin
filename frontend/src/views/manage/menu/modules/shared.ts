const LAYOUT_PREFIX = 'layout.';
const VIEW_PREFIX = 'view.';
const FIRST_LEVEL_ROUTE_COMPONENT_SPLIT = '$';

/** 翻译不存在时保留后端菜单名称，不把国际化 key 当作显示文本。 */
export function resolveMenuLabel(
  key: App.I18n.I18nKey | null | undefined,
  menuName: string,
  locale: { translate: (key: App.I18n.I18nKey) => string; exists: (key: string) => boolean }
): string {
  return key && locale.exists(key) ? locale.translate(key) : menuName;
}

export function getLayoutAndPage(component?: string | null) {
  if (component === 'Layout') return { layout: 'base', page: '' };
  if (component === 'ParentView') return { layout: '', page: '' };
  if (component && !component.startsWith(LAYOUT_PREFIX) && !component.startsWith(VIEW_PREFIX)) {
    return { layout: '', page: component };
  }
  let layout = '';
  let page = '';

  const [layoutOrPage = '', pageItem = ''] = component?.split(FIRST_LEVEL_ROUTE_COMPONENT_SPLIT) || [];

  layout = getLayout(layoutOrPage);
  page = getPage(pageItem || layoutOrPage);

  return { layout, page };
}

function getLayout(layout: string) {
  return layout.startsWith(LAYOUT_PREFIX) ? layout.replace(LAYOUT_PREFIX, '') : '';
}

function getPage(page: string) {
  return page.startsWith(VIEW_PREFIX) ? page.replace(VIEW_PREFIX, '') : '';
}

export function transformLayoutAndPageToComponent(layout: string, page: string) {
  const hasLayout = Boolean(layout);
  const hasPage = Boolean(page);

  if (hasLayout && hasPage) {
    return `${LAYOUT_PREFIX}${layout}${FIRST_LEVEL_ROUTE_COMPONENT_SPLIT}${VIEW_PREFIX}${page}`;
  }

  if (hasLayout) {
    return `${LAYOUT_PREFIX}${layout}`;
  }

  if (hasPage) {
    if (page.includes('/')) return page;
    return `${VIEW_PREFIX}${page}`;
  }

  return '';
}

/** 展示字段的编辑不能悄悄重写旧格式组件或多参数路径。 */
export function resolveMenuRouteSubmission(
  model: { layout: string; page: string; routePath: string; pathParam: string },
  original?: { component?: string | null; routePath: string } | null
) {
  const initialComponent = getLayoutAndPage(original?.component);
  const initialPath = getPathParamFromRoutePath(original?.routePath ?? '');
  return {
    component:
      original && model.layout === initialComponent.layout && model.page === initialComponent.page
        ? (original.component ?? '')
        : transformLayoutAndPageToComponent(model.layout, model.page),
    routePath:
      original && model.routePath === initialPath.path && model.pathParam === initialPath.param
        ? original.routePath
        : getRoutePathWithParam(model.routePath, model.pathParam)
  };
}

/**
 * Get route name by route path
 *
 * @param routeName
 */
export function getRoutePathByRouteName(routeName: string) {
  return `/${routeName.replace(/_/g, '/')}`;
}

/**
 * Get path param from route path
 *
 * @param routePath route path
 */
export function getPathParamFromRoutePath(routePath: string) {
  const separator = routePath.indexOf('/:');

  return {
    path: separator < 0 ? routePath : routePath.slice(0, separator),
    param: separator < 0 ? '' : routePath.slice(separator + 2)
  };
}

/**
 * Get route path with param
 *
 * @param routePath route path
 * @param param path param
 */
export function getRoutePathWithParam(routePath: string, param: string) {
  if (param.trim()) {
    return `${routePath}/:${param}`;
  }

  return routePath;
}
