const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { ref } = require('vue');
const ts = require('typescript');

function functions(relativePath, names, bindings) {
  const source = fs.readFileSync(path.join(__dirname, relativePath), 'utf8');
  const script = source.includes('<script') ? source.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1] : source;
  const parsed = ts.createSourceFile('test.tsx', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const selected = parsed.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text));
  const declared = selected.map(node => node.name.text);
  const context = { exports: {}, ...bindings };
  vm.runInNewContext(
    ts.transpileModule(
      `${selected.map(node => node.getText(parsed)).join('\n')}\nthis.api = { ${declared.join(', ')} };`,
      { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }
    ).outputText,
    context
  );
  return context.api;
}

for (const file of [
  '../src/views/task/run/modules/run-create-drawer.vue',
  '../src/components/business/run-execute-modal/index.vue'
]) {
  test(`${file} previews before creating and reuses the confirmation request ID on retries`, async () => {
    const previews = [];
    const writes = [];
    const bindings = {
      form: {
        version: 7,
        pool: 3,
        hosts: [1],
        groups: [],
        tags: [],
        hostStrategy: 'inherit',
        serialBatch: null,
        maxFailPercentage: null
      },
      fields: ref([]),
      values: ref({}),
      inputVars: ref({}),
      selectedHosts: ref([{ id: 1 }]),
      formRef: ref({ validate: async () => true }),
      validateRequiredParams: () => true,
      saving: ref(false),
      submitting: ref(false),
      visible: ref(true),
      props: { visible: true },
      previewRequestId: 0,
      preview: ref(null),
      previewVisible: ref(false),
      pendingPayload: ref(null),
      fetchPreviewWorkflowRun: async payload => {
        previews.push(payload);
        return { data: preview('legacy-preview') };
      },
      fetchCreateWorkflowRun: async payload => {
        writes.push(payload);
        return { error: new Error('response lost') };
      },
      window: { $message: { warning() {}, success() {} } },
      emit() {},
      router: { push() {} }
    };
    const api = functions(file, ['submit', 'confirmRun', 'invalidatePreview', 'buildPayload'], bindings);
    await api.submit();
    assert.equal(writes.length, 0);
    assert.equal(previews.length, 1);
    assert.equal(bindings.previewVisible.value, true);
    await api.confirmRun();
    await api.confirmRun();
    assert.deepEqual(
      writes.map(payload => payload.executionRequestId),
      ['legacy-preview', 'legacy-preview']
    );
  });
}

function preview(executionRequestId) {
  return {
    executionRequestId,
    targets: [{ hostId: 3 }],
    targetFingerprint: 'targets',
    confirmationFingerprint: 'confirmation'
  };
}

for (const [file, apiName] of [
  ['ops/quick-execute/script', 'fetchCreateQuickCommandRun'],
  ['ops/quick-execute/playbook', 'fetchCreatePlaybookRun'],
  ['ops/quick-execute/module', 'fetchCreateModuleRun'],
  ['task/run-create', 'fetchCreateWorkflowRun']
]) {
  test(`${file} preserves the preview request ID across network retries, then uses a fresh preview ID`, async () => {
    const writes = [];
    const currentPreview = ref(preview('first-preview'));
    const api = functions(`../src/views/${file}/index.vue`, ['confirmRun'], {
      previewRequestId: 0,
      preview: currentPreview,
      pendingPayload: ref({ name: 'example' }),
      submitting: ref(false),
      loadingCommandVersions: ref(false),
      previewVisible: ref(true),
      router: { push() {} },
      window: { $message: { success() {} } },
      [apiName]: async payload => {
        writes.push(payload);
        return { error: new Error('response lost') };
      }
    });
    await api.confirmRun();
    await api.confirmRun();
    assert.deepEqual(
      writes.map(payload => payload.executionRequestId),
      ['first-preview', 'first-preview']
    );
    currentPreview.value = preview('second-preview');
    await api.confirmRun();
    assert.equal(writes[2].executionRequestId, 'second-preview');
  });
}

for (const apiName of ['fetchRunScheduledJobNow', 'fetchRunTaskTicket']) {
  test(`${apiName} forwards the same preview request ID on repeated confirmation`, async () => {
    const writes = [];
    const api = functions('../src/service/api/jobs.ts', [apiName], {
      request: async config => {
        writes.push(config.data);
        return {};
      }
    });
    await api[apiName](7, preview('same-preview'));
    await api[apiName](7, preview('same-preview'));
    assert.deepEqual(
      writes.map(payload => payload.executionRequestId),
      ['same-preview', 'same-preview']
    );
  });
}

test('Jenkins cancellation confirms that remote builds can continue before calling the cancellation API', async () => {
  const events = [];
  const api = functions('../src/views/task/run-detail/index.vue', ['onCancel'], {
    runId: ref(7),
    operating: ref(false),
    domain: ref('task'),
    requestScope: { signal: undefined },
    nodes: ref([{ nodeType: 'jenkins' }]),
    run: ref({ graphSnapshot: {} }),
    window: {
      $message: { success() {} },
      $messageBox: {
        confirm: async message => {
          events.push(message);
        }
      }
    },
    fetchCancelRun: async () => {
      events.push('cancel-api');
      return {};
    },
    loadRun: async () => {},
    loadNodes: async () => {},
    $t: key => key
  });
  await api.onCancel();
  assert.equal(events.length, 2);
  assert.match(events[0], /取消将停止本平台等待；已触发的 Jenkins 构建可能继续运行/);
  assert.equal(events[1], 'cancel-api');
});
