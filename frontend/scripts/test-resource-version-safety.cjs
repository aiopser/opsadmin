const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadFunctions(relative, names, bindings) {
  const source = fs.readFileSync(path.join(__dirname, relative), 'utf8');
  const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const parsed = ts.createSourceFile('component.tsx', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const functions = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name.text));
  const context = { ...bindings };
  vm.runInNewContext(ts.transpileModule(functions.map(node => node.getText(parsed)).join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText, context);
  return context;
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
const resources = '../src/views/automation/resources/modules/command-page.vue';

test('version save is locked before async validation and always unlocks', async () => {
  const validation = deferred();
  let requests = 0;
  const context = loadFunctions(resources, ['handleSaveVersion'], {
    versionSubmitting: { value: false }, currentCommand: { value: { id: 1 } },
    versionEditorId: 1, editingVersionId: { value: null },
    versionFormRef: { value: { validate: () => validation.promise } }, versionForm: { value: {} },
    buildVersionPayload: () => ({}), fetchAddCommandVersion: async () => { requests += 1; return { error: null }; },
    getData() {}, window: { $message: { success() {} } }, versionFormVisible: { value: true }, versionFormBaseline: { value: '' }, resetVersionForm() {}, loadVersions() {}
  });
  const first = context.handleSaveVersion();
  const second = context.handleSaveVersion();
  validation.resolve(true);
  await Promise.all([first, second]);
  assert.equal(requests, 1);
  assert.equal(context.versionSubmitting.value, false);
  context.fetchAddCommandVersion = async () => { throw new Error('network'); };
  await assert.rejects(context.handleSaveVersion(), /network/);
  assert.equal(context.versionSubmitting.value, false);
});

test('late publication cannot update another resource', async () => {
  const response = deferred();
  let loaded = 0;
  const context = loadFunctions(resources, ['handlePublishVersion'], {
    versionActionBusy: { value: false }, versionEditorId: 1,
    currentCommand: { value: { id: 1, status: 'draft' } },
    ElMessageBox: { confirm: async () => true }, fetchPublishCommandVersion: () => response.promise,
    getData() {}, loadVersions() { loaded += 1; }, window: { $message: { success() {} } }
  });
  const pending = context.handlePublishVersion({ id: 10, version: 3 });
  await Promise.resolve();
  context.currentCommand.value = { id: 2, status: 'draft' };
  context.versionEditorId = 2;
  response.resolve({ error: null });
  await pending;
  assert.equal(context.currentCommand.value.status, 'draft');
  assert.equal(loaded, 0);
  assert.equal(context.versionActionBusy.value, false);
});

test('late Playbook selection cannot replace the current resource version', async () => {
  const responses = [deferred(), deferred()];
  const context = loadFunctions('../src/views/ops/quick-execute/playbook/index.vue', ['onPlaybookSelected', 'applyPlaybookVersion'], {
    playbookRequestId: 0, playbookSource: { value: 'library' },
    selectedPlaybookVersionId: { value: null }, playbookVersions: { value: [] }, playbooks: { value: [] },
    form: { selectedPlaybookId: 1, playbookContent: '' }, fetchGetCommandVersions: id => responses[id - 1].promise
  });
  const first = context.onPlaybookSelected(1);
  context.form.selectedPlaybookId = 2;
  const second = context.onPlaybookSelected(2);
  responses[1].resolve({ data: [{ id: 20, status: 'published', content: 'B' }] });
  await second;
  responses[0].resolve({ data: [{ id: 10, status: 'published', content: 'A' }] });
  await first;
  assert.equal(context.form.playbookContent, 'B');
  assert.equal(context.selectedPlaybookVersionId.value, 20);
});


test('closing version list while loading content does not reopen the editor', async () => {
  const response = deferred();
  let opened = 0;
  const context = loadFunctions(resources, ['openContentEditor'], {
    openVersionDrawer: () => response.promise,
    currentCommand: { value: { id: 1 } }, versionDrawerVisible: { value: true },
    openNewVersionForm() { opened += 1; }
  });
  const pending = context.openContentEditor({ id: 1 });
  context.versionDrawerVisible.value = false;
  response.resolve(true);
  await pending;
  assert.equal(opened, 0);
});

test('an old drawer close animation cannot clear the newly opened editor', () => {
  const context = loadFunctions(resources, ['onVersionFormClosed'], {
    versionFormVisible: { value: true }, versionEditorId: 2,
    versionForm: { value: { content: 'new draft' } }, editingVersionId: { value: 20 },
    currentCommand: { value: { id: 2 } }, versionDrawerVisible: { value: false },
    createDefaultVersionForm: () => ({ content: '' })
  });
  context.onVersionFormClosed();
  assert.equal(context.versionForm.value.content, 'new draft');
  assert.equal(context.editingVersionId.value, 20);
});

for (const [kind, apiName] of [['module', 'fetchCreateModuleRun'], ['playbook', 'fetchCreatePlaybookRun']]) {
  test(`${kind} confirmation ignores a late response after leaving the page`, async () => {
    const response = deferred();
    let navigations = 0;
    const context = loadFunctions(`../src/views/ops/quick-execute/${kind}/index.vue`, ['confirmRun'], {
      previewRequestId: 1, submitting: { value: false }, previewVisible: { value: true },
      pendingPayload: { value: { checkMode: false } },
      preview: { value: { targets: [] } },
      [apiName]: () => response.promise,
      router: { push() { navigations += 1; } }, window: { $message: { success() {} } }
    });
    const pending = context.confirmRun();
    context.previewRequestId += 1;
    context.pendingPayload.value = null;
    response.resolve({ data: { id: 1 }, error: null });
    await pending;
    assert.equal(navigations, 0);
    assert.equal(context.submitting.value, false);
  });
}
