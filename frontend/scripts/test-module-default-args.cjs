const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/views/ops/quick-execute/module/index.vue'), 'utf8');
const functionSource = source.match(/function versionDefaultArgs\([^]*?\n}/)[0];
const context = {};
vm.runInNewContext(ts.transpileModule(functionSource, {}).outputText, context);
const serialize = defaults => context.versionDefaultArgs({ defaultVars: { module_args: defaults } });
const examples = [
  { msg: "hello world's test" },
  { path: '/tmp/example' },
  { name: ['nginx', 'git'] },
  { headers: { Authorization: 'Bearer example' } },
  { emptyArray: [], emptyObject: {} },
  { nested: { groups: ['中文', { quote: "it's fine" }] } },
  { enabled: false, retries: 3, empty: null },
  { text: '["keep-as-string"]' },
  { cmd: 'echo hello', chdir: '/tmp' }
];
examples.forEach(values => assert.deepEqual(JSON.parse(serialize(values)), values));
assert.equal(serialize('echo hello world'), 'echo hello world');
console.log('native module defaults preserve scalar types and free-form arguments');
