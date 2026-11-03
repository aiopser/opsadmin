const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

function functions(filename, names, bindings) {
  const source = fs
    .readFileSync(path.join(__dirname, '../src/views/monitoring', filename, 'index.vue'), 'utf8')
    .match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const parsed = ts.createSourceFile('page.ts', source, ts.ScriptTarget.Latest, true);
  const code = parsed.statements
    .filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name.text))
    .map(node => node.getText(parsed))
    .join('\n');
  const context = { ...bindings };
  vm.runInNewContext(
    ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText,
    context
  );
  return context;
}
function deferred() {
  let finish;
  const promise = new Promise(resolve => {
    finish = resolve;
  });
  return { promise, finish };
}

test('JumpServer records ignore a previous connection response', async () => {
  const a = deferred();
  const b = deferred();
  const api = functions('integrations', ['showRecords'], {
    selected: {},
    selectedRecord: {},
    records: {},
    recordVisible: {},
    recordSequence: 0,
    fetchJumpServerRecords: id => (id === 1 ? a.promise : b.promise)
  });
  const first = api.showRecords({ id: 1 });
  const second = api.showRecords({ id: 2 });
  b.finish({ data: ['B'], error: null });
  await second;
  a.finish({ data: ['A'], error: null });
  await first;
  assert.deepEqual(api.records.value, ['B']);
});

test('JumpServer confirmation does not submit the same preview twice', async () => {
  const response = deferred();
  let calls = 0;
  const api = functions('integrations', ['confirm'], {
    selected: { value: { id: 1 } },
    preview: { value: { id: 9 } },
    confirming: { value: false },
    syncVisible: {},
    window: { $message: { success() {} } },
    showRecords: async () => {},
    confirmJumpServer: () => {
      calls += 1;
      return response.promise;
    }
  });
  const a = api.confirm();
  const b = api.confirm();
  assert.equal(calls, 1);
  response.finish({ error: null });
  await Promise.all([a, b]);
});

test('Enrollment preview rejects responses for a previously selected policy', async () => {
  const a = deferred();
  const b = deferred();
  const api = functions('policies', ['showPreview'], {
    requestSequence: 0,
    selected: {},
    preview: {},
    previewVisible: {},
    previewLoading: {},
    previewPage: {},
    previewEnrollmentPolicy: id => (id === 1 ? a.promise : b.promise)
  });
  const first = api.showPreview({ id: 1 });
  const second = api.showPreview({ id: 2 });
  b.finish({ data: { name: 'B' }, error: null });
  await second;
  a.finish({ data: { name: 'A' }, error: null });
  await first;
  assert.equal(api.preview.value.name, 'B');
});

test('Consul file read failure preserves the editor draft', async () => {
  const api = functions('consul-template', ['readFromHost', 'isCurrentDraft'], {
    form: { value: { host: 7, path: '/etc/ct/app.hcl', content: 'draft' } },
    editor: { value: true },
    editorSequence: 0,
    readRemote: async () => null,
    window: { $message: { warning() {} } }
  });
  await api.readFromHost();
  assert.equal(api.form.value.content, 'draft');
});

test('Consul file read does not replace edits made while reading', async () => {
  const response = deferred();
  const api = functions('consul-template', ['readFromHost', 'isCurrentDraft'], {
    form: { value: { host: 7, path: '/etc/ct/app.hcl', content: 'draft' } },
    editor: { value: true },
    editorSequence: 0,
    readRemote: () => response.promise,
    window: { $message: { warning() {} } }
  });
  const pending = api.readFromHost();
  api.form.value.content = 'edited-while-reading';
  response.finish({ exists: true, content: 'remote' });
  await pending;
  assert.equal(api.form.value.content, 'edited-while-reading');
});
