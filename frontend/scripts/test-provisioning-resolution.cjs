const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { computed, effectScope, nextTick, reactive, ref, shallowRef, watch, onScopeDispose } = require('vue');
const ts = require('typescript');

const componentPath = path.join(__dirname, '../src/views/task/provisioning/manual-resolution.vue');
const source = fs.readFileSync(componentPath, 'utf8').match(/<script[^>]*>([^]*?)<\/script>/)[1];
const parsed = ts.createSourceFile('manual-resolution.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
const script = parsed.statements.filter(node => !ts.isImportDeclaration(node)).map(node => node.getText(parsed)).join('\n');
const compiled = ts.transpileModule(`${script}\nglobalThis.hooks = { open, loadPreview, confirm, visible, preview, errorMessage, form, acknowledged, canConfirm, evidenceReference, comment };`, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const proof = {
  previewId: 'proof-one', digest: 'a'.repeat(64), expiresAt: '2099-01-01T00:00:00Z',
  stateVersionId: 3, stateDigest: 'b'.repeat(64), serial: 5, instanceIds: ['i-one'],
  observedAssets: [{ instanceId: 'i-one', hostname: 'web', internal_ip: '10.1.1.1' }], notice: '已回读'
};

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function mount({ previewResult, confirmationResult } = {}) {
  const calls = [];
  const emitted = [];
  const props = reactive({ record: { id: 1, name: 'web', source_name: 'Cloud', region: 'cn-shanghai', parameters: { count: 1 }, execution_status: 'needs_reconciliation', allowed_actions: ['resolution-preview', 'resolution-confirm'] } });
  const scope = effectScope();
  const context = {
    computed, ref, shallowRef, watch, onScopeDispose, props,
    defineOptions() {}, defineProps: () => props, defineEmits: () => event => emitted.push(event),
    useNow: () => ref(new Date('2026-10-23T00:00:00Z')),
    formatLocalDateTime: value => value,
    previewResourceResolution: async id => { calls.push({ kind: 'preview', id }); return previewResult ? previewResult() : { data: proof, error: null }; },
    confirmResourceResolution: async (id, data) => { calls.push({ kind: 'confirm', id, data }); return confirmationResult ? confirmationResult() : { data: {}, error: null }; },
    window: { $message: { success() {} } }
  };
  scope.run(() => vm.runInNewContext(compiled, context));
  context.hooks.form.value = { validate: async () => true };
  return { ...context.hooks, context, calls, emitted, props, dispose: () => scope.stop() };
}

test('human confirmation submits frozen proof and evidence then refreshes', async () => {
  const view = mount();
  try {
    await view.open();
    view.context.hooks.evidenceReference.value = ' INC-001 ';
    view.context.hooks.comment.value = ' 云控制台与工单已核实 ';
    view.acknowledged.value = true;
    await view.confirm();
    const submitted = view.calls.find(call => call.kind === 'confirm');
    assert.equal(JSON.stringify(submitted.data), JSON.stringify({ previewId: proof.previewId, digest: proof.digest, evidenceReference: 'INC-001', comment: '云控制台与工单已核实' }));
    assert.deepEqual(view.emitted, ['updated']);
    assert.equal(view.visible.value, false);
  } finally { view.dispose(); }
});

test('missing state stays visible as a reason and cannot be confirmed', async () => {
  const view = mount({ previewResult: async () => ({ data: null, error: { response: { data: { msg: '缺少 state 证据' } } } }) });
  try {
    await view.open();
    assert.equal(view.preview.value, undefined);
    assert.match(view.errorMessage.value, /缺少 state/);
    await view.confirm();
    assert.equal(view.calls.filter(call => call.kind === 'confirm').length, 0);
    assert.equal(view.props.record.execution_status, 'needs_reconciliation');
  } finally { view.dispose(); }
});

test('closing preview drops a late response', async () => {
  const gate = deferred();
  const view = mount({ previewResult: () => gate.promise });
  try {
    const pending = view.open();
    view.visible.value = false;
    await nextTick();
    gate.resolve({ data: proof, error: null });
    await pending;
    assert.equal(view.preview.value, undefined);
  } finally { view.dispose(); }
});

test('expired proof and revoked review permission cannot submit', async () => {
  const view = mount();
  try {
    await view.open();
    view.acknowledged.value = true;
    view.preview.value = { ...proof, expiresAt: '2020-01-01T00:00:00Z' };
    await view.confirm();
    assert.equal(view.calls.filter(call => call.kind === 'confirm').length, 0);
    view.preview.value = proof;
    view.props.record.allowed_actions = [];
    await nextTick();
    await view.confirm();
    assert.equal(view.calls.filter(call => call.kind === 'confirm').length, 0);
  } finally { view.dispose(); }
});

test('switching applications fences a confirmation response', async () => {
  const gate = deferred();
  const view = mount({ confirmationResult: () => gate.promise });
  try {
    await view.open();
    view.acknowledged.value = true;
    const pending = view.confirm();
    await nextTick();
    view.props.record = { ...view.props.record, id: 2 };
    await nextTick();
    gate.resolve({ data: {}, error: null });
    await pending;
    assert.deepEqual(view.emitted, []);
  } finally { view.dispose(); }
});
