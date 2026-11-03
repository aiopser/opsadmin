const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');

const helpers = {};
vm.runInNewContext(
  ts.transpileModule(
    fs.readFileSync(path.join(__dirname, '../src/views/cmdb/source/modules/cloud-preview.ts'), 'utf8'),
    {
      compilerOptions: { module: ts.ModuleKind.CommonJS }
    }
  ).outputText,
  { exports: helpers }
);

test('only new and changed cloud instances can be selected for synchronization', () => {
  assert.equal(helpers.canSyncRow({ action: 'create' }), true);
  assert.equal(helpers.canSyncRow({ action: 'update' }), true);
  assert.equal(helpers.canSyncRow({ action: 'unchanged' }), false);
  assert.equal(helpers.canSyncRow({ action: 'invalid' }), false);
});

test('cloud preview keeps missing and zero values distinct and displays fractional memory', () => {
  assert.equal(helpers.formatMemory(512), '512 MiB');
  assert.equal(helpers.formatMemory(1536), '1.5 GiB');
  assert.equal(helpers.formatMemory(undefined), '—');
  assert.equal(helpers.formatValue(0), '0');
  assert.equal(helpers.formatValue(null), '—');
  assert.equal(helpers.actionLabel('unchanged'), '未变化');
});

test('preview warns about absent specs, but accepts an explicit zero data disk', () => {
  assert.equal(helpers.countIncompleteSpecs([{ specs: {} }, {}]), 2);
  assert.equal(
    helpers.countIncompleteSpecs([
      {
        specs: {
          cpu_cores: 4,
          memory_mb: 8192,
          system_disk_gb: 40,
          data_disk_gb: 0,
          region: 'cn-shanghai'
        }
      }
    ]),
    0
  );
  assert.equal(helpers.countIncompleteSpecs([]), 0);
});
