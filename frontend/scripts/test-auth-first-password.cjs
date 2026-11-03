const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const vue = require('vue');
const ts = require('typescript');

function loadTs(relativePath, bindings, functions) {
  const source = fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
  const script = source.includes('<script') ? source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1] : source;
  const parsed = ts.createSourceFile(
    'test.ts',
    script.replaceAll('import.meta.env', 'runtimeEnv'),
    ts.ScriptTarget.Latest,
    true
  );
  const selected = parsed.statements.filter(
    node =>
      !ts.isImportDeclaration(node) &&
      (!functions || (ts.isFunctionDeclaration(node) && functions.includes(node.name?.text)))
  );
  const context = { exports: {}, ...bindings };
  vm.runInNewContext(
    ts.transpileModule(selected.map(node => node.getText(parsed)).join('\n'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
    }).outputText,
    context
  );
  return context;
}

function authApi(data) {
  const calls = [];
  const context = loadTs('../src/service/api/auth.ts', {
    request: async config => {
      calls.push(config.url);
      return { data, error: null, response: {} };
    }
  });
  return { ...context.exports, calls };
}

test('auth DTO maps the required-password flag from its backend snakeCase field', async () => {
  const api = authApi({ id: 9, username: 'reset-user', must_change_password: true });
  assert.equal((await api.fetchGetUserInfo()).data.mustChangePassword, true);
  assert.equal((await api.fetchGetUserProfile()).data.mustChangePassword, true);
  const existing = authApi({ id: 9, username: 'existing-user' });
  assert.equal((await existing.fetchGetUserInfo()).data.mustChangePassword, false);
});

function authStore(mustChangePassword) {
  const navigation = [];
  const guards = [];
  const calls = [];
  const storage = new Map([
    ['token', 'stored-access'],
    ['refreshToken', 'stored-refresh']
  ]);
  let store;
  const scope = vue.effectScope();
  let context;
  scope.run(() => {
    context = loadTs('../src/store/modules/auth/index.ts', {
      ...vue,
      runtimeEnv: { VITE_AUTH_ROUTE_MODE: 'dynamic' },
      SetupStoreId: { Auth: 'auth' },
      defineStore: (_name, setup) => () => {
        if (store) return store;
        store = { $reset() {} };
        Object.assign(store, setup());
        return store;
      },
      useRoute: () => ({ meta: { constant: true } }),
      useRouteStore: () => ({ resetStore() {} }),
      useTabStore: () => ({ clearTabs() {}, cacheTabs() {} }),
      useRouterPush: () => ({
        toLogin: async () => navigation.push('login'),
        redirectFromLogin: async () => navigation.push('default'),
        routerPushByKey: async name => navigation.push(name)
      }),
      router: {
        beforeEach: guard => {
          guards.push(guard);
          return () => {};
        }
      },
      useLoading: () => ({ loading: vue.ref(false), startLoading() {}, endLoading() {} }),
      getToken: () => storage.get('token'),
      localStg: {
        get: key => storage.get(key),
        set: (key, value) => storage.set(key, value),
        remove: key => storage.delete(key)
      },
      clearAuthStorage: () => storage.clear(),
      fetchLogin: async () => {
        calls.push('login');
        return { data: { token: 'access', refreshToken: 'refresh' }, error: null };
      },
      fetchGetUserInfo: async () => {
        calls.push('me');
        return { data: { userId: '9', userName: 'user', roles: [], buttons: [], mustChangePassword }, error: null };
      },
      window: { $notification: { success() {} } },
      $t: key => key
    });
    context.exports.useAuthStore();
  });
  return { store, navigation, guards, calls, dispose: () => scope.stop() };
}

test('first-password login navigates directly to user center without loading the normal landing page', async t => {
  const auth = authStore(true);
  t.after(auth.dispose);
  await auth.store.login('user', 'initial');
  assert.deepEqual(auth.calls, ['login', 'me']);
  assert.deepEqual(auth.navigation, ['user-center']);
});

test('a persisted initial-password session redirects business routes before their pages mount', async t => {
  const auth = authStore(true);
  t.after(auth.dispose);
  await auth.store.initUserInfo();
  assert.equal(auth.guards.length, 1);
  assert.equal(auth.guards[0]({ name: 'home' }).name, 'user-center');
  assert.equal(auth.guards[0]({ name: 'task_templates' }).name, 'user-center');
  assert.equal(auth.guards[0]({ name: 'user-center' }), undefined);
});

test('ordinary users keep their normal redirect and may navigate business routes', async t => {
  const auth = authStore(false);
  t.after(auth.dispose);
  await auth.store.login('user', 'existing');
  assert.deepEqual(auth.navigation, ['default']);
  assert.equal(auth.guards[0]({ name: 'home' }), undefined);
});

test('password update clears credentials and awaits return to login', async () => {
  const events = [];
  const passwordModel = vue.ref({ oldPassword: 'old', newPassword: 'new', confirmPassword: 'new' });
  const context = loadTs(
    '../src/views/user-center/index.vue',
    {
      passwordModel,
      passwordSaving: vue.ref(false),
      validatePassword: async () => events.push('validate'),
      fetchUpdateUserPassword: async () => {
        events.push('password');
        return {};
      },
      resetPasswordForm: () => events.push('reset'),
      authStore: {
        resetStore: async () => {
          await Promise.resolve();
          events.push('logout');
        }
      },
      window: { $message: { success() {} } },
      $t: key => key
    },
    ['createPasswordModel', 'handleSavePassword']
  );
  await context.handleSavePassword();
  assert.equal(events.at(-1), 'logout');
  assert.equal(passwordModel.value.oldPassword, '');
});
