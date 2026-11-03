const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { ref, watch, nextTick } = require('vue');
const ts = require('typescript');

const shared = {};
vm.runInNewContext(
  ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/views/manage/menu/modules/shared.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
  }).outputText,
  { exports: shared }
);

test('opening edit and changing only the icon preserves the route and translation key', async () => {
  const sfc = fs.readFileSync(path.join(__dirname, '../src/views/manage/menu/modules/menu-operate-modal.vue'), 'utf8');
  const script = sfc.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const source = ts.createSourceFile('menu.ts', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const names = [
    'createDefaultModel',
    'handleInitModel',
    'handleUpdateRoutePathByRouteName',
    'handleUpdateI18nKeyByRouteName',
    'handleRouteNameChange',
    'getSubmitParams'
  ];
  const selected = source.statements
    .filter(
      node =>
        (ts.isFunctionDeclaration(node) && names.includes(node.name?.text)) ||
        (ts.isExpressionStatement(node) &&
          ts.isCallExpression(node.expression) &&
          node.expression.expression.getText(source) === 'watch' &&
          node.expression.arguments[0].getText(source).includes('model.value.routeName'))
    )
    .map(node => node.getText(source))
    .join('\n');
  const model = ref({ routeName: '' });
  const context = {
    ...shared,
    model,
    watch,
    props: {
      operateType: 'edit',
      rowData: {
        routeName: 'User',
        routePath: 'user',
        i18nKey: null,
        component: 'view.manage_user',
        menuName: '用户管理',
        icon: ''
      }
    },
    $te: key => key === 'route.manage_user'
  };
  vm.createContext(context);
  vm.runInContext(ts.transpileModule(selected, {}).outputText, context);
  context.handleInitModel();
  await nextTick();
  model.value.icon = 'ic:round-person';
  await nextTick();
  assert.equal(model.value.routePath, 'user');
  assert.equal(model.value.i18nKey, null);
  assert.equal(model.value.menuName, '用户管理');
  context.handleRouteNameChange('RenamedUser');
  assert.equal(model.value.routePath, 'user');
  context.props.operateType = 'addChild';
  model.value.parentId = 1;
  context.handleRouteNameChange('U');
  context.handleRouteNameChange('User');
  assert.equal(model.value.routePath, 'user');
  context.props.operateType = 'edit';
  for (const component of [
    'system/user/index',
    'view.system/user/index',
    'Layout',
    'ParentView',
    'layout.base$view.manage_user'
  ]) {
    context.props.rowData.component = component;
    context.props.rowData.routePath = '/users/:id/children/:childId';
    context.handleInitModel();
    // Every edit must settle its watchers before checking submitted values.
    // eslint-disable-next-line no-await-in-loop
    await nextTick();
    model.value.icon = 'ic:round-person';
    const submitted = context.getSubmitParams();
    assert.equal(submitted.component, component);
    assert.equal(submitted.routePath, '/users/:id/children/:childId');
  }
});

test('unknown translation keys fall back to the configured Chinese menu name', () => {
  assert.equal(
    shared.resolveMenuLabel('route.User', '用户管理', { translate: key => key, exists: () => false }),
    '用户管理'
  );
  assert.equal(
    shared.resolveMenuLabel('route.manage_user', '用户管理', { translate: () => 'Users', exists: () => true }),
    'Users'
  );
});

test('legacy pages and paths with multiple parameters round trip without losing segments', () => {
  const original = '/users/:id/children/:childId';
  const parsed = shared.getPathParamFromRoutePath(original);
  assert.equal(parsed.param, 'id/children/:childId');
  assert.equal(shared.getRoutePathWithParam(parsed.path, parsed.param), original);
  assert.equal(shared.transformLayoutAndPageToComponent('', 'system/user/index'), 'system/user/index');
});
