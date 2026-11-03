const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { computed, effectScope, nextTick, ref, watch } = require('vue');
const ts = require('typescript');
const shared = {};
vm.runInNewContext(
  ts.transpileModule(
    fs.readFileSync(path.join(__dirname, '../src/components/business/cloud-resource-picker/shared.ts'), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS } }
  ).outputText,
  { exports: shared }
);
assert.equal(shared.acceptResponse(1, 2), false);
assert.equal(shared.acceptResponse(2, 2), true);
assert.equal(shared.capacityLabel(null), '未知');
assert.equal(shared.capacityLabel(0), '0');
const initial = {
  name: 'web',
  count: 1,
  image_id: 'old-image',
  instance_type: 'old-type',
  zone: 'old-zone',
  vpc_id: 'old-vpc',
  subnet_id: 'old-subnet',
  security_group_ids: ['old-sg'],
  system_disk_gb: 40
};
const reset = shared.resetDependencies(initial, 'account');
assert.equal(reset.image_id, '');
assert.equal(reset.subnet_id, '');
assert.equal(reset.security_group_ids.length, 0);
assert.equal(initial.image_id, 'old-image');
assert.equal(shared.resetDependencies(initial, 'zone').instance_type, '');
assert.equal(shared.resetDependencies(initial, 'vpc').zone, 'old-zone');
console.log('cloud resource picker contract passed');

test('actual drawer and picker preserve the selected zone', async () => {
  const drawer = fs.readFileSync(path.join(__dirname, '../src/views/task/provisioning/request-drawer.vue'), 'utf8');
  const querySource = drawer.match(/function catalogQuery\([^]*?\n}/)[0];
  const parameters = ref({ ...initial, zone: '' });
  const drawerContext = { model: ref({ version: 1, credential: 1, region: 'cn-shanghai' }), parameters };
  vm.runInNewContext(
    ts.transpileModule(`${querySource}\nglobalThis.query = catalogQuery;`, {
      compilerOptions: { module: ts.ModuleKind.CommonJS }
    }).outputText,
    drawerContext
  );
  const picker = fs
    .readFileSync(path.join(__dirname, '../src/components/business/cloud-resource-picker/index.vue'), 'utf8')
    .match(/<script[^>]*>([^]*?)<\/script>/)[1];
  const source = ts.createSourceFile('picker.ts', picker, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const watcher = source.statements
    .find(
      node =>
        ts.isExpressionStatement(node) &&
        ts.isCallExpression(node.expression) &&
        node.expression.expression.getText(source) === 'watch' &&
        node.getText(source).includes('props.query')
    )
    .getText(source);
  const scope = effectScope();
  try {
    scope.run(() =>
      vm.runInNewContext(
        ts.transpileModule(watcher, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText,
        {
          watch,
          props: {
            get query() {
              return drawerContext.query('zones');
            },
            multiple: false
          },
          model: computed({
            get: () => parameters.value.zone,
            set: value => {
              parameters.value.zone = value;
            }
          }),
          sequence: ref(0),
          items: ref([]),
          cursor: ref(null),
          observedAt: ref(''),
          search: ref(''),
          loading: ref(false),
          load() {}
        }
      )
    );
    parameters.value.zone = 'cn-shanghai-a';
    await nextTick();
    assert.equal(parameters.value.zone, 'cn-shanghai-a');
    drawerContext.model.value.region = 'cn-beijing';
    await nextTick();
    assert.equal(parameters.value.zone, '');
  } finally {
    scope.stop();
  }
});
