const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, '../src/views/manage/config/modules/config-state.ts'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }
).outputText;
const exported = {};
vm.runInNewContext(compiled, { exports: exported });
const { mergeConfigSnapshot, persistConfigChanges, loadConfigPages } = exported;

test('saving freezes submitted values and leaves later typing dirty', async () => {
  let finish;
  const gate = new Promise(resolve => {
    finish = resolve;
  });
  const draft = { name: 'submitted' };
  const pending = persistConfigChanges([{ configKey: 'name' }], draft, async () => gate);
  draft.name = 'later typing';
  finish({});
  const result = await pending;
  assert.equal(result.saved.name, 'submitted');
  assert.notEqual(result.saved.name, draft.name);
});

test('partial failure records successful values only, including thrown errors', async () => {
  const result = await persistConfigChanges(
    [{ configKey: 'a' }, { configKey: 'b' }, { configKey: 'c' }],
    { a: 'A', b: 'B', c: 'C' },
    async row => {
      if (row.configKey === 'b') return { error: new Error('rejected') };
      if (row.configKey === 'c') throw new Error('offline');
      return {};
    }
  );
  assert.equal(JSON.stringify(result.saved), '{"a":"A"}');
  assert.equal(Array.from(result.failedKeys).join(','), 'b,c');
});

test('new configuration reload preserves drafts and refreshes clean values', () => {
  const result = mergeConfigSnapshot(
    [
      { configKey: 'a', configValue: 'server' },
      { configKey: 'b', configValue: 'new server' },
      { configKey: 'new', configValue: 'created' }
    ],
    { a: 'unsaved', b: 'old' },
    { a: 'old', b: 'old' }
  );
  assert.equal(result.drafts.a, 'unsaved');
  assert.equal(result.saved.a, 'server');
  assert.equal(result.drafts.b, 'new server');
  assert.equal(result.drafts.new, 'created');
});

test('loads beyond the first 200 rows', async () => {
  const records = Array.from({ length: 205 }, (_, id) => ({ id, configKey: `key${id}`, configValue: '' }));
  const result = await loadConfigPages(async (current, size) => ({
    records: records.slice((current - 1) * size, current * size),
    total: 205
  }));
  assert.equal(result.length, 205);
  assert.equal(result[204].configKey, 'key204');
});

test('pagination failure never returns a partial configuration snapshot', async () => {
  await assert.rejects(
    loadConfigPages(async current =>
      current === 1 ? { records: [{ id: 1, configKey: 'a', configValue: '' }], total: 2 } : null
    )
  );
});
