const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

function workflowApi() {
  const stored = { inputSchema: { fields: [{ name: 'release_tag' }] }, globalVars: { environment: 'test' } };
  const exported = {};
  const compiled = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, '../src/service/api/automation.ts'), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }
  ).outputText;
  vm.runInNewContext(compiled, {
    exports: exported,
    require(name) {
      assert.equal(name, '../request');
      return {
        async request({ url, method, data }) {
          assert.equal(url, '/api/v1/automation/workflow-versions/42');
          assert.equal(method, 'patch');
          // The serializer's public input fields are camelCase. Nested keys are user data.
          assert.ok(Object.hasOwn(data, 'inputSchema'));
          assert.ok(Object.hasOwn(data, 'globalVars'));
          stored.inputSchema = data.inputSchema;
          stored.globalVars = data.globalVars;
          return { data: { ...stored }, error: null };
        }
      };
    }
  });
  return { api: exported, stored };
}

test('workflow version update sends camelCase fields and preserves nested parameter names', async () => {
  const { api, stored } = workflowApi();
  const payload = {
    inputSchema: { fields: [{ name: 'release_tag', required: true }] },
    globalVars: { application_name: 'example', regionCode: 'test' }
  };
  const result = await api.fetchUpdateWorkflowVersion(42, payload);
  assert.equal(result.error, null);
  assert.deepEqual(stored, payload);
});

test('empty input schema and global variables are sent explicitly to clear saved configuration', async () => {
  const { api, stored } = workflowApi();
  await api.fetchUpdateWorkflowVersion(42, { inputSchema: {}, globalVars: {} });
  assert.deepEqual(stored, { inputSchema: {}, globalVars: {} });
});
