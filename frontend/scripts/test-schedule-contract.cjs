const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('typescript');

const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, '../src/views/task/schedule/shared.ts'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } }
).outputText;
const exported = {};
vm.runInNewContext(compiled, { exports: exported });
const { humanizeCron } = exported;

test('every minute and every hour are distinct schedules', () => {
  assert.equal(humanizeCron('* * * * *'), '每分钟触发一次');
  assert.equal(humanizeCron('0 * * * *'), '每小时的第 0 分触发');
  assert.equal(humanizeCron('*/5 * * * *'), '每 5 分钟触发一次');
});

test('calendar restrictions are never silently dropped', () => {
  assert.equal(humanizeCron('0 2 * * 1-5'), '工作日 02:00 触发');
  assert.equal(humanizeCron('0 2 15 * *'), '每月 15 日 02:00 触发');
  assert.equal(humanizeCron('*/5 * * * 1-5'), '自定义周期，请确认表达式正确');
  assert.equal(humanizeCron('0 */2 * 12 *'), '自定义周期，请确认表达式正确');
});
