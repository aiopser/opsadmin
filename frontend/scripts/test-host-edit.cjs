const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { ref, shallowRef, watch, nextTick } = require('vue');
const ts = require('typescript');
const shared = {};
vm.runInNewContext(
  ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/views/cmdb/host/modules/shared.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS }
  }).outputText,
  { exports: shared }
);

function hostEditor(overrides = {}) {
  const file = fs.readFileSync(path.join(__dirname, '../src/views/cmdb/host/modules/host-list.vue'), 'utf8');
  const script = file.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const source = ts.createSourceFile('host.tsx', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const names = [
    'createDefaultForm',
    'buildFormFromRow',
    'openOperateDrawer',
    'loadFormOptions',
    'saveHostRelations',
    'handleSubmit'
  ];
  const selected = source.statements
    .filter(
      node =>
        (ts.isFunctionDeclaration(node) && names.includes(node.name?.text)) ||
        (ts.isExpressionStatement(node) &&
          ts.isCallExpression(node.expression) &&
          node.expression.expression.getText(source) === 'watch' &&
          node.expression.arguments[0].getText(source).includes('props.query'))
    )
    .map(node => node.getText(source))
    .join('\n');
  const writes = [];
  const messages = [];
  const context = {
    ...shared,
    ref,
    shallowRef,
    watch,
    props: { query: {} },
    searchParams: ref({ current: 3 }),
    operateType: ref('edit'),
    openSections: ref([]),
    formModel: ref({}),
    drawerVisible: ref(false),
    submitting: ref(false),
    relationsReady: ref(false),
    formRef: ref({ validate: async () => true }),
    credentialOptions: ref([]),
    groupOptions: ref([]),
    tagOptions: ref([]),
    assetSourceOptions: ref([]),
    optionsLoaded: false,
    fetchGetCredentialRefList: async () => ({ data: { records: [] } }),
    fetchGetHostGroupList: async () => ({ data: { records: [] } }),
    fetchGetTagList: async () => ({ data: { records: [] } }),
    fetchGetAssetSourceList: async () => ({ data: { records: [] } }),
    fetchGetHostRelations: async () => ({ data: { groupIds: ['1'], tagIds: ['2'] } }),
    fetchUpdateHostRelations: async (id, payload) => {
      writes.push({ id, payload });
      return {};
    },
    fetchUpdateHost: async (id, payload) => {
      writes.push({ id, payload });
      return { data: { id } };
    },
    fetchAddHost: async payload => {
      writes.push({ payload });
      return { data: { id: 10 } };
    },
    resolveTagIds: async ids => ids,
    getData: () => {},
    getDataByPage: () => {},
    emit: () => {},
    window: {
      $message: {
        success: value => messages.push(['success', value]),
        warning: value => messages.push(['warning', value]),
        error: value => messages.push(['error', value])
      }
    },
    ...overrides
  };
  vm.createContext(context);
  vm.runInContext(
    ts.transpileModule(selected, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText,
    context
  );
  return { context, writes, messages };
}

const row = { id: 1, hostname: 'host', internalIp: '10.0.0.1', memoryMb: 512, osFamily: 'linux', groupIds: ['1'] };

test('changing only a host name preserves sub-GB and fractional-GB memory', async () => {
  for (const memoryMb of [512, 1536, 8193]) {
    const { context, writes } = hostEditor();
    // eslint-disable-next-line no-await-in-loop
    await context.openOperateDrawer('edit', { ...row, memoryMb });
    context.formModel.value.hostname = 'renamed';
    // eslint-disable-next-line no-await-in-loop
    await context.handleSubmit();
    assert.equal(writes[0].payload.memory_mb, memoryMb);
    assert.equal(writes[1].payload.tagIds.join(','), '2');
  }
});

test('failed relation loading prevents opening or submitting an empty replacement', async () => {
  const { context, writes } = hostEditor({ fetchGetHostRelations: async () => ({ error: new Error('offline') }) });
  await context.openOperateDrawer('edit', row);
  assert.equal(context.drawerVisible.value, false);
  await context.handleSubmit();
  assert.equal(writes.length, 0);
});

test('relation write failure keeps the editor open and never announces complete success', async () => {
  const { context, messages } = hostEditor({ fetchUpdateHostRelations: async () => ({ error: new Error('offline') }) });
  await context.openOperateDrawer('edit', row);
  await context.handleSubmit();
  assert.equal(context.drawerVisible.value, true);
  assert.equal(
    messages.some(([kind]) => kind === 'success'),
    false
  );
  assert.equal(context.submitting.value, false);
});

test('a failed first option load can be retried', async () => {
  let attempts = 0;
  const { context } = hostEditor({
    fetchGetCredentialRefList: async () => {
      attempts += 1;
      return attempts === 1 ? { error: new Error('offline') } : { data: { records: [{ id: 7, name: 'ssh' }] } };
    }
  });
  await context.loadFormOptions();
  await context.loadFormOptions();
  assert.equal(attempts, 2);
  assert.equal(context.credentialOptions.value[0].value, 7);
});

test('switching groups resets the pagination controller together with the request', async () => {
  const props = { query: ref({ groupId: 1 }) };
  const selected = ref({ query: props.query.value });
  let resetCalls = 0;
  const { context } = hostEditor({
    props: selected.value,
    getDataByPage: () => {
      resetCalls += 1;
    }
  });
  context.props.query = { groupId: 2 };
  await nextTick();
  assert.equal(resetCalls, 1);
});
