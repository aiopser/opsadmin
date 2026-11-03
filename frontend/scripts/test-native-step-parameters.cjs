const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const source = readFileSync(join(__dirname, '../src/views/task/flow-design/shared.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const context = { exports: {} };
vm.runInNewContext(compiled, context);
const { nativeParameterConfig, nativeParameterText } = context.exports;
const plain = value => JSON.parse(JSON.stringify(value));

test('Ansible native parameters preserve expressions and typed nested values', () => {
  const params = { host: '{{ inventory_hostname }}', count: 2, enabled: true, packages: ['nginx'] };
  const text = nativeParameterText('playbook', { extraVars: params });
  assert.deepEqual(plain(nativeParameterConfig('playbook', text)), { extraVars: params });
});

test('module native text and historical object arguments round trip', () => {
  assert.equal(nativeParameterText('module', { moduleArgs: 'name=nginx state=started' }), 'name=nginx state=started');
  assert.deepEqual(plain(nativeParameterConfig('module', 'name=nginx state=started')), { args: 'name=nginx state=started' });
  assert.deepEqual(plain(nativeParameterConfig('module', '{"name":"nginx"}')), { args: { name: 'nginx' } });
});

test('empty optional parameters add no override and API keeps its executor contract', () => {
  assert.deepEqual(plain(nativeParameterConfig('script', '')), {});
  assert.deepEqual(plain(nativeParameterConfig('api', 'curl http://example.invalid')), {});
  assert.equal(nativeParameterText('api', { extraVars: { token: 'x' } }), '');
});

test('scalar and list variable blocks are rejected before saving', () => {
  for (const text of ['null', '[]', '1', '"text"', '{broken']) {
    assert.throws(() => nativeParameterConfig('playbook', text));
  }
});


test('module free-form commands retain native Jinja and shell grouping', () => {
  for (const text of ['{{ executable }} --version', '{ echo hello; }']) {
    assert.deepEqual(plain(nativeParameterConfig('module', text)), { args: text });
  }
});


test('step host settings are inherited until an explicit override is enabled', () => {
  const settings = { hostPolicy: 'platform', overrideHostSettings: false, hostStrategy: 'serial', forks: 20, serialBatch: 5, maxFailPercentage: 10 };
  assert.deepEqual(plain(context.exports.stepHostConfig('script', settings)), {});
  assert.deepEqual(plain(context.exports.stepHostConfig('script', { ...settings, overrideHostSettings: true })), { hostStrategy: 'serial', maxFailPercentage: 10 });
});

test('native playbooks do not serialize hidden platform strategy overrides', () => {
  const settings = { hostPolicy: 'native', overrideHostSettings: true, hostStrategy: 'rolling', forks: 20, serialBatch: 2, maxFailPercentage: 5 };
  assert.deepEqual(plain(context.exports.stepHostConfig('playbook', settings)), { hostPolicy: 'native' });
  assert.deepEqual(plain(context.exports.stepHostConfig('playbook', { ...settings, hostPolicy: 'platform' })), { hostPolicy: 'platform', hostStrategy: 'rolling', forks: 20, serialBatch: 2, maxFailPercentage: 5 });
});
