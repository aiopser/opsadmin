const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const vue = require('vue');
const ts = require('typescript');

const scriptPath = '../src/views/ops/quick-execute/script/index.vue';
const flowPath = '../src/views/task/flow-design/index.vue';
const nativeContext = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/views/task/flow-design/shared.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS }
}).outputText, nativeContext);

const gitPath = '../src/views/automation/resources/modules/command-page.vue';

function deferred() {
  let resolve;
  const promise = new Promise(done => {
    resolve = done;
  });
  return { promise, resolve };
}

function component(relativePath, names, overrides = {}) {
  const { select, ...bindings } = overrides;
  const source = fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
  const script = source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const parsed = ts.createSourceFile('component.tsx', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const selected = parsed.statements.filter(node => !ts.isImportDeclaration(node) && (!select || select(node, parsed)));
  const unmount = [];
  const messages = [];
  const context = {
    ...vue,
    onBeforeUnmount: callback => unmount.push(callback),
    defineOptions() {},
    useRouter: () => ({ push() {} }),
    useAuth: () => ({ hasAuth: () => true }),
    window: {
      $message: Object.fromEntries(
        ['success', 'warning', 'error'].map(kind => [kind, value => messages.push([kind, value])])
      )
    },
    ...bindings
  };
  const scope = vue.effectScope();
  scope.run(() =>
    vm.runInNewContext(
      ts.transpileModule(
        `${selected.map(node => node.getText(parsed)).join('\n')}\nthis.api = { ${names.join(', ')} };`,
        { compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.Preserve } }
      ).outputText,
      context
    )
  );
  return {
    ...context.api,
    messages,
    dispose() {
      unmount.forEach(callback => callback());
      scope.stop();
    }
  };
}

function scriptEditor(overrides = {}) {
  const previews = [];
  const runs = [];
  const editor = component(
    scriptPath,
    [
      'form',
      'formRef',
      'extraVarsRef',
      'commandSource',
      'commandType',
      'sourceCommandVersionId',
      'commandVersions',
      'selectedVersionId',
      'submitting',
      'previewVisible',
      'pendingPayload',
      'onScriptConfirm',
      'loadCommandVersions',
      'applySelectedVersion',
      'onReset',
      'onSubmit',
      'confirmRun',
      'onScriptFileChange'
    ],
    {
      fetchGetCommandVersions: async id => ({ data: [version(id)], error: null }),
      fetchPreviewQuickCommandRun: async payload => {
        previews.push(payload);
        return { data: { targets: [], targetFingerprint: 'targets', confirmationFingerprint: 'confirm' } };
      },
      fetchCreateQuickCommandRun: async payload => {
        runs.push(payload);
        return { data: { id: 1 } };
      },
      ...overrides
    }
  );
  editor.commandSource.value = 'library';
  editor.form.hosts = [{ id: 1, osFamily: 'linux', hostname: 'test' }];
  editor.formRef.value = { validate: async () => true, clearValidate() {} };
  editor.extraVarsRef.value = { getValue: () => ({}), reset() {} };
  return { ...editor, previews, runs };
}

function version(id, commandType = 'linux_shell') {
  return { id: id * 10, commandType, status: 'published', content: `script-${id}`, version: 1 };
}

test('script selection ignores a slower response for a previously selected script', async t => {
  const first = deferred();
  const second = deferred();
  const editor = scriptEditor({ fetchGetCommandVersions: id => (id === 1 ? first.promise : second.promise) });
  t.after(editor.dispose);
  const a = editor.onScriptConfirm({ id: 1, name: 'A' });
  const b = editor.onScriptConfirm({ id: 2, name: 'B' });
  second.resolve({ data: [version(2)] });
  await b;
  first.resolve({ data: [version(1)] });
  await a;
  assert.equal(editor.form.selectedCommand.name, 'B');
  assert.equal(editor.form.commandContent, 'script-2');
  assert.equal(editor.sourceCommandVersionId.value, 20);
});

test('loading a replacement script clears old execution content and blocks preview', async t => {
  const pending = deferred();
  let loading = false;
  const editor = scriptEditor({
    fetchGetCommandVersions: id => (loading ? pending.promise : Promise.resolve({ data: [version(id)] }))
  });
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 1, name: 'A' });
  loading = true;
  const next = editor.onScriptConfirm({ id: 2, name: 'B' });
  assert.equal(editor.form.commandContent, '');
  assert.equal(editor.sourceCommandVersionId.value, null);
  await editor.onSubmit();
  assert.equal(editor.previews.length, 0);
  pending.resolve({ data: [version(2)] });
  await next;
});

test('reset, source switching and component close each invalidate pending script loads', async () => {
  for (const action of ['reset', 'source', 'close']) {
    const pending = deferred();
    const editor = scriptEditor({ fetchGetCommandVersions: () => pending.promise });
    const loading = editor.onScriptConfirm({ id: 1, name: 'A' });
    if (action === 'reset') editor.onReset();
    if (action === 'source') editor.commandSource.value = 'manual';
    if (action === 'close') editor.dispose();
    // eslint-disable-next-line no-await-in-loop
    await vue.nextTick();
    pending.resolve({ data: [version(1)] });
    // eslint-disable-next-line no-await-in-loop
    await loading;
    assert.equal(editor.form.commandContent, '', action);
    assert.equal(editor.sourceCommandVersionId.value, null, action);
    editor.dispose();
  }
});

test('script type changes invalidate old versions before a pending replacement resolves', async t => {
  const pending = deferred();
  let calls = 0;
  const editor = scriptEditor({
    fetchGetCommandVersions: () => {
      calls += 1;
      return calls === 1 ? Promise.resolve({ data: [version(1)] }) : pending.promise;
    }
  });
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 1, name: 'A' });
  editor.commandType.value = 'python';
  assert.equal(editor.sourceCommandVersionId.value, null);
  assert.equal(editor.form.commandContent, '');
  pending.resolve({ data: [version(1, 'python')] });
  await new Promise(resolve => {
    setImmediate(resolve);
  });
  assert.equal(editor.form.commandContent, 'script-1');
});

test('repeated clicks during validation produce only one script preview and one confirmed run', async t => {
  const validate = deferred();
  const editor = scriptEditor();
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 1, name: 'A' });
  editor.formRef.value.validate = () => validate.promise;
  const first = editor.onSubmit();
  const second = editor.onSubmit();
  validate.resolve(true);
  await Promise.all([first, second]);
  assert.equal(editor.previews.length, 1);
  await Promise.all([editor.confirmRun(), editor.confirmRun()]);
  assert.equal(editor.runs.length, 1);
});

test('reset or switching scripts invalidates an already open preview', async t => {
  const editor = scriptEditor();
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 1, name: 'A' });
  await editor.onSubmit();
  assert.equal(editor.previewVisible.value, true);
  editor.onReset();
  await editor.confirmRun();
  assert.equal(editor.runs.length, 0);
  assert.equal(editor.previewVisible.value, false);
});

test('a preview that finishes after reset cannot reopen the confirmation dialog', async t => {
  const pending = deferred();
  const editor = scriptEditor({ fetchPreviewQuickCommandRun: () => pending.promise });
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 1, name: 'A' });
  const submitting = editor.onSubmit();
  await Promise.resolve();
  editor.onReset();
  pending.resolve({ data: { targets: [], targetFingerprint: 'old', confirmationFingerprint: 'old' } });
  await submitting;
  assert.equal(editor.previewVisible.value, false);
  assert.equal(editor.pendingPayload.value, null);
});

test('a late upload read cannot restore script content after reset', t => {
  const readers = [];
  function FileReader() {
    const reader = { readAsText() {}, result: 'old file' };
    readers.push(reader);
    return reader;
  }
  const editor = scriptEditor({ FileReader });
  t.after(editor.dispose);
  editor.commandSource.value = 'upload';
  editor.onScriptFileChange({ raw: { name: 'example.sh', size: 10 } });
  editor.onReset();
  readers[0].onload();
  assert.equal(editor.form.commandContent, '');
});

test('a script with no matching published version stays empty and cannot preview execution', async t => {
  const editor = scriptEditor({ fetchGetCommandVersions: async () => ({ data: [] }) });
  t.after(editor.dispose);
  editor.form.commandContent = 'old script';
  editor.sourceCommandVersionId.value = 10;
  await editor.onScriptConfirm({ id: 2, name: 'empty' });
  await editor.onSubmit();
  assert.equal(editor.form.commandContent, '');
  assert.equal(editor.sourceCommandVersionId.value, null);
  assert.equal(editor.previews.length, 0);
});

test('fallback script type follows the latest supported published version', async t => {
  const editor = scriptEditor({
    fetchGetCommandVersions: async () => ({ data: [version(2, 'windows_powershell'), version(1, 'python')] })
  });
  t.after(editor.dispose);
  await editor.onScriptConfirm({ id: 2, name: 'latest type' });
  await new Promise(resolve => {
    setImmediate(resolve);
  });
  assert.equal(editor.commandType.value, 'windows_powershell');
  assert.equal(editor.form.commandContent, 'script-2');
});

function selectFunctions(names) {
  return node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text);
}

function flowEditor(overrides = {}) {
  const updates = [];
  const published = [];
  const steps = vue.ref([
    {
      key: 'step1',
      name: 'submitted',
      type: 'api',
      hostPolicy: 'native',
      overrideHostSettings: false,
      hostStrategy: 'inherit',
      forks: null,
      serialBatch: null,
      maxFailPercentage: null,
      checkMode: 'inherit',
      sourceConfig: {},
      nativeParametersText: '',
      inputMapping: { nested: { value: 'saved' } },
      outputExtractorsText: '',
      timeoutSeconds: 60,
      maxAttempts: 1,
      resourceId: 7
    }
  ]);
  const inputSchemaText = vue.ref('{}');
  const globalVarsText = vue.ref('{"environment":"submitted"}');
  const stepsSnapshot = vue.ref('');
  const textsSnapshot = vue.ref('');
  const editor = component(flowPath, ['saveDraft', 'onValidate', 'backToTemplates'], {
    steps,
    inputSchemaText,
    globalVarsText,
    stepsSnapshot,
    textsSnapshot,
    versionInfo: vue.ref({ id: 7, status: 'draft' }),
    editable: vue.ref(true),
    saving: vue.ref(false),
    saveErrors: vue.ref([]),
    ANSIBLE_TYPES: new Set(['script', 'command', 'module', 'playbook']),
    isDirty: vue.computed(
      () =>
        JSON.stringify(steps.value) !== stepsSnapshot.value ||
        inputSchemaText.value !== textsSnapshot.value
    ),
    parseJsonObject: JSON.parse,
    mappingHasBrokenJson: () => false,
    nativeParameterConfig: nativeContext.exports.nativeParameterConfig,
    stepHostConfig: nativeContext.exports.stepHostConfig,
    fetchUpdateWorkflowGraph: async (id, graph) => {
      updates.push({ id, graph });
      return { data: { valid: true } };
    },
    fetchUpdateWorkflowVersion: async (id, payload) => {
      updates.push({ id, payload });
      return {};
    },
    fetchPublishWorkflowVersion: async id => {
      published.push(id);
      return { data: { id, status: 'published' } };
    },
    ...overrides,
    select: selectFunctions([
      'saveDraft',
      'stepToNode',
      'collectSavePayload',
      'buildGraph',
      'syncStepsSnapshot',
      'syncTextsSnapshot',
      'publishCurrent',
      'onValidate',
      'backToTemplates'
    ])
  });
  return { ...editor, steps, inputSchemaText, globalVarsText, stepsSnapshot, textsSnapshot, updates, published };
}

test('workflow success records the submitted snapshot and preserves later changes as dirty', async t => {
  const pending = deferred();
  const editor = flowEditor({ fetchUpdateWorkflowGraph: () => pending.promise });
  t.after(editor.dispose);
  const submittedSteps = JSON.stringify(editor.steps.value);
  const submittedTexts = editor.inputSchemaText.value;
  const saving = editor.saveDraft();
  editor.steps.value[0].name = 'later edit';
  editor.inputSchemaText.value = '{"fields":[]}';
  pending.resolve({ data: { valid: true } });
  await saving;
  assert.equal(editor.stepsSnapshot.value, submittedSteps);
  assert.equal(editor.textsSnapshot.value, submittedTexts);
  assert.notEqual(JSON.stringify(editor.steps.value), editor.stepsSnapshot.value);
});

test('workflow request graph owns a snapshot of nested parameter mappings', async t => {
  const pending = deferred();
  let submitted;
  const editor = flowEditor({
    fetchUpdateWorkflowGraph: (_id, graph) => {
      submitted = graph;
      return pending.promise;
    }
  });
  editor.steps.value[0].type = 'jenkins';
  t.after(editor.dispose);
  const saving = editor.saveDraft();
  editor.steps.value[0].inputMapping.nested.value = 'later';
  assert.equal(submitted.nodes[1].inputMapping.nested.value, 'saved');
  pending.resolve({ data: { valid: true } });
  await saving;
});

test('workflow edits made during save prevent publishing stale content', async t => {
  const pending = deferred();
  const editor = flowEditor({ fetchUpdateWorkflowGraph: () => pending.promise });
  t.after(editor.dispose);
  const saving = editor.saveDraft(true);
  editor.steps.value[0].name = 'later edit';
  pending.resolve({ data: { valid: true } });
  assert.equal(await saving, false);
  assert.equal(editor.published.length, 0);
});

test('workflow duplicate saves share one request window and failed patch preserves dirty state', async t => {
  const pending = deferred();
  let calls = 0;
  const editor = flowEditor({
    fetchUpdateWorkflowGraph: () => {
      calls += 1;
      return pending.promise;
    },
    fetchUpdateWorkflowVersion: async () => ({ error: new Error('offline') })
  });
  t.after(editor.dispose);
  const first = editor.saveDraft();
  const second = editor.saveDraft();
  pending.resolve({ data: { valid: true } });
  await Promise.all([first, second]);
  assert.equal(calls, 1);
  assert.equal(editor.stepsSnapshot.value, '');
});

function gitEditor(overrides = {}) {
  const names = [
    'invalidateGitSelection',
    'handleGitRepoChange',
    'handleGitRefChange',
    'searchGitFiles',
    'handleGitFileChange',
    'onScriptSourceChange'
  ];
  const state = {
    gitRepoId: vue.ref(1),
    gitRef: vue.ref('A'),
    gitFilePath: vue.ref('playbook.yml'),
    gitFileOptions: vue.ref(['playbook.yml']),
    gitRepoOptions: vue.ref([{ id: 1, branch: 'main' }]),
    gitLoadingFiles: vue.ref(false),
    gitLoadingContent: vue.ref(false),
    gitFilesRequestId: 0,
    gitContentRequestId: 0,
    cloneRequestId: 0,
    cloneScriptId: vue.ref(null),
    localFileName: vue.ref(''),
    scriptSource: vue.ref('git'),
    drawerVisible: vue.ref(true),
    formModel: vue.ref({ content: '' }),
    currentTemplate: '',
    fetchGetGitRepositoryFiles: async () => ({ data: { files: [] } }),
    fetchLoadGitRepositoryFile: async () => ({ data: { content: 'loaded' } }),
    ...overrides
  };
  const editor = component(
    gitPath,
    names.filter(name => name !== 'invalidateGitSelection' && name !== 'handleGitRefChange'),
    {
      ...state,
      select: (node, parsed) =>
        selectFunctions(names)(node) ||
        (ts.isExpressionStatement(node) &&
          ts.isCallExpression(node.expression) &&
          ['watch', 'onBeforeUnmount'].includes(node.expression.expression.getText(parsed)))
    }
  );
  return { ...editor, ...state };
}

test('Git ref changes clear selection and reject old content, even for the same repository and path', async t => {
  const pending = deferred();
  const editor = gitEditor({ fetchLoadGitRepositoryFile: () => pending.promise });
  t.after(editor.dispose);
  const loading = editor.handleGitFileChange('playbook.yml');
  editor.gitRef.value = 'B';
  await vue.nextTick();
  pending.resolve({ data: { content: 'branch A' } });
  await loading;
  assert.equal(editor.gitFilePath.value, null);
  assert.equal(editor.formModel.value.content, '');
  assert.equal(editor.gitLoadingContent.value, false);
});

test('Git file lists are bound to the requested ref', async t => {
  const pending = deferred();
  const editor = gitEditor({ fetchGetGitRepositoryFiles: () => pending.promise });
  t.after(editor.dispose);
  const loading = editor.searchGitFiles('');
  editor.gitRef.value = 'B';
  await vue.nextTick();
  pending.resolve({ data: { files: ['only-in-A.yml'] } });
  await loading;
  assert.equal(editor.gitFileOptions.value.length, 0);
});

test('clearing a Git file, changing source and closing the drawer reject pending content', async () => {
  for (const action of ['clear', 'source', 'close']) {
    const pending = deferred();
    const editor = gitEditor({ fetchLoadGitRepositoryFile: () => pending.promise });
    const loading = editor.handleGitFileChange('playbook.yml');
    if (action === 'clear') {
      editor.gitFilePath.value = null;
      editor.handleGitFileChange(null);
    }
    if (action === 'source') {
      editor.scriptSource.value = 'manual';
      editor.onScriptSourceChange();
    }
    if (action === 'close') editor.drawerVisible.value = false;
    // eslint-disable-next-line no-await-in-loop
    await vue.nextTick();
    pending.resolve({ data: { content: 'obsolete' } });
    // eslint-disable-next-line no-await-in-loop
    await loading;
    assert.equal(editor.formModel.value.content, '', action);
    assert.equal(editor.gitLoadingContent.value, false, action);
    editor.dispose();
  }
});

test('dynamic navigation uses registered route names', () => {
  const flow = fs.readFileSync(path.join(__dirname, flowPath), 'utf8');
  const run = fs.readFileSync(path.join(__dirname, '../src/views/task/run-create/index.vue'), 'utf8');
  assert.match(flow, /router\.push\(\{ name: 'task_templates' \}\)/);
  assert.match(run, /router\.push\(\{ name: 'task_run-detail', params: \{ id: data\.id \} \}\)/);
});

test('script selection renders the normalized camelCase DTO fields', () => {
  const source = fs.readFileSync(
    path.join(__dirname, '../src/components/business/script-select-modal/index.vue'),
    'utf8'
  );
  assert.match(source, /getRiskMeta\(row\.riskLevel\)/);
  assert.match(source, /formatDay\(row\.updatedAt\)/);
  assert.doesNotMatch(source, /row\.(risk_level|updated_at)/);
});


test('workflow native parameters replace generic mappings and preserve unrelated configuration', async t => {
  const editor = flowEditor();
  t.after(editor.dispose);
  Object.assign(editor.steps.value[0], {
    type: 'playbook', commandVersionId: 12, hostStrategy: 'inherit', checkMode: 'inherit',
    sourceConfig: { customSetting: 'retained', extraVars: { old: true }, forks: 5 },
    nativeParametersText: '{"host":"{{ inventory_hostname }}","count":2}'
  });
  await editor.saveDraft();
  const node = editor.updates.find(item => item.graph).graph.nodes.find(item => item.id === 'step1');
  assert.equal(node.config.customSetting, 'retained');
  assert.equal(node.config.extraVars.host, '{{ inventory_hostname }}');
  assert.equal(node.config.extraVars.count, 2);
  assert.equal(node.config.forks, undefined);
  assert.equal(Object.keys(node.inputMapping).length, 0);
});

test('clearing an optional native block removes the previous override', async t => {
  const editor = flowEditor();
  t.after(editor.dispose);
  Object.assign(editor.steps.value[0], {
    type: 'script', commandVersionId: 12, hostStrategy: 'inherit', checkMode: 'inherit',
    sourceConfig: { environment: { old: true } }, nativeParametersText: ''
  });
  await editor.saveDraft();
  const node = editor.updates.find(item => item.graph).graph.nodes.find(item => item.id === 'step1');
  assert.equal(node.config, undefined);
});

test('API structured HTTP node configuration is preserved when saving', async t => {
  const editor = flowEditor();
  t.after(editor.dispose);
  editor.steps.value[0].sourceConfig = { method: 'POST', customSetting: { enabled: true } };
  await editor.saveDraft();
  const node = editor.updates.find(item => item.graph).graph.nodes.find(item => item.id === 'step1');
  assert.equal(node.config.method, 'POST');
  assert.equal(node.config.customSetting.enabled, true);
});
