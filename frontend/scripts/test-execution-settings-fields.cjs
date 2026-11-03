const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { parse, compileScript } = require('@vue/compiler-sfc');
const { createSSRApp, defineComponent, h } = require('vue');
const { renderToString } = require('vue/server-renderer');
const ts = require('typescript');

const filename = path.join(__dirname, '../src/components/business/execution-settings-fields/index.vue');
const { descriptor } = parse(fs.readFileSync(filename, 'utf8'), { filename });
const compiled = compileScript(descriptor, { id: 'execution-settings-test', inlineTemplate: true });
const javascript = ts.transpileModule(compiled.content, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const exported = {};
vm.runInNewContext(javascript, { exports: exported, require });

async function renderFields(hostStrategy) {
  const inputs = [];
  const changes = [];
  const app = createSSRApp(exported.default, {
    hostStrategy,
    forks: null,
    serialBatch: null,
    maxFailPercentage: null,
    timeoutSeconds: null,
    'onUpdate:forks': value => changes.push(['forks', value]),
    'onUpdate:serialBatch': value => changes.push(['serialBatch', value]),
    'onUpdate:maxFailPercentage': value => changes.push(['maxFailPercentage', value]),
    'onUpdate:timeoutSeconds': value => changes.push(['timeoutSeconds', value])
  });
  const passthrough = defineComponent({
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    }
  });
  ['ElFormItem', 'ElRadioGroup', 'ElRadio'].forEach(name => app.component(name, passthrough));
  app.component('ElInputNumber', defineComponent({
    inheritAttrs: false,
    setup(_props, { attrs }) {
      inputs.push(attrs);
      return () => h('input');
    }
  }));
  const html = await renderToString(app);
  return { inputs, changes, html };
}

test('only rolling and inherited strategies expose batch size; serial disables forks', async () => {
  for (const strategy of ['inherit', 'parallel', 'serial', 'rolling']) {
    const { inputs, html } = await renderFields(strategy);
    const showBatch = ['inherit', 'rolling'].includes(strategy);
    assert.equal(inputs.length, showBatch ? 4 : 3);
    const forks = inputs[showBatch ? 1 : 0];
    assert.equal(forks.disabled, strategy === 'serial');
    if (strategy === 'serial') assert.match(html, /串行策略固定为 1/);
  }
});

test('nullable settings preserve values and expose consistent numeric limits and updates', async () => {
  const { inputs, changes, html } = await renderFields('rolling');
  assert.deepEqual(inputs.map(input => [input.min, input.max ?? null, input.precision]), [
    [1, null, 0], [1, 100, 0], [0, 100, 0], [1, 86400, 0]
  ]);
  inputs.forEach(input => assert.equal(input.modelValue, null));
  inputs[2]['onUpdate:modelValue'](0);
  inputs[3]['onUpdate:modelValue'](600);
  inputs[3]['onUpdate:modelValue'](undefined);
  assert.deepEqual(changes, [['maxFailPercentage', 0], ['timeoutSeconds', 600], ['timeoutSeconds', null]]);
  assert.match(html, /0 表示零容忍/);
  assert.match(html, /整个流程超时（秒）/);
});

test('all four entry points bind each setting without replacing their complete form', () => {
  const files = [
    'components/business/run-execute-modal/index.vue',
    'views/task/run-create/index.vue',
    'views/task/run/modules/ticket-create-drawer.vue',
    'views/task/schedule/index.vue'
  ];
  files.forEach(file => {
    const source = fs.readFileSync(path.join(__dirname, '../src', file), 'utf8');
    const component = source.match(/<ExecutionSettingsFields[\s\S]*?\/>/)[0];
    const fields = file.includes('schedule')
      ? ['host_strategy', 'forks', 'serial_batch', 'max_fail_percentage', 'timeout_seconds']
      : ['hostStrategy', 'forks', 'serialBatch', 'maxFailPercentage', 'timeoutSeconds'];
    ['host-strategy', 'forks', 'serial-batch', 'max-fail-percentage', 'timeout-seconds'].forEach((model, index) => {
      assert.ok(component.includes(`v-model:${model}="form.${fields[index]}"`), `${file}: ${model}`);
    });
  });
});
