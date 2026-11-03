const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const vue = require('vue');
const { parse, compileScript } = require('vue/compiler-sfc');
const { renderToString } = require('vue/server-renderer');
const ts = require('typescript');

const fields = {};
vm.runInNewContext(
  ts.transpileModule(
    fs.readFileSync(path.join(__dirname, '../src/views/manage/config/modules/config-fields.ts'), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.CommonJS } }
  ).outputText,
  { exports: fields }
);
const sfc = fs.readFileSync(path.join(__dirname, '../src/views/manage/config/modules/config-field-row.vue'), 'utf8');
const { descriptor } = parse(sfc);
const compiled = compileScript(descriptor, { id: 'config-field-row-contract', inlineTemplate: true });
const rowComponent = {};
vm.runInNewContext(
  ts.transpileModule(compiled.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
  }).outputText,
  {
    exports: rowComponent,
    require(name) {
      if (name === 'vue') return vue;
      assert.equal(name, './config-fields');
      return fields;
    }
  }
);

async function renderRow(item) {
  const app = vue.createSSRApp(rowComponent.default, { item, value: '', disabled: false });
  const stub = vue.defineComponent({
    setup:
      (_props, { attrs, slots }) =>
      () =>
        vue.h('div', attrs, slots.default?.())
  });
  ['ElInput', 'ElInputNumber', 'ElTag', 'ElSwitch', 'ElAvatar', 'ElTooltip', 'icon-ic-round-person'].forEach(name =>
    app.component(name, stub)
  );
  return renderToString(app);
}

test('the current configuration row renders its displayed name and active runtime hint', async () => {
  const item = { configKey: 'security.login.max_failures', configName: '登录失败次数上限', remark: '' };
  const html = await renderRow(item);
  assert.match(html, /连续登录失败次数/);
  assert.match(html, /15 分钟/);
  assert.doesNotMatch(html, /暂未生效/);
  assert.equal(fields.resolveFieldDef(item.configKey).inactiveReason, undefined);
});

test('inactive configuration rows still display the inactive marker and reason', async () => {
  const item = { configKey: 'file.media.base_url', configName: '媒体地址', remark: '配置说明' };
  const html = await renderRow(item);
  assert.match(html, /媒体地址/);
  assert.match(html, /配置说明/);
  assert.match(html, /暂未生效/);
  assert.match(html, /当前媒体访问路径由服务端部署配置决定/);
});

test('settings without runtime consumers are explicitly inactive without a relogin promise', () => {
  for (const key of [
    'basic.user.default_avatar',
    'security.jwt.access_token_seconds',
    'log.operation.retention_days',
    'file.media.base_url'
  ]) {
    const field = fields.resolveFieldDef(key);
    assert.ok(field.inactiveReason, key);
    assert.doesNotMatch(field.hint || '', /重新登录生效/);
  }
  assert.equal(fields.resolveFieldDef('basic.system.name').inactiveReason, undefined);
});
