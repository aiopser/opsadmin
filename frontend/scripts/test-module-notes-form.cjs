const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const vue = require('vue');
const { parse, compileScript } = require('vue/compiler-sfc');
const { renderToString } = require('vue/server-renderer');
const ts = require('typescript');
const { descriptor } = parse(fs.readFileSync(path.join(__dirname, '../src/views/automation/resources/modules/version-form-fields.vue'), 'utf8'));
const compiled = compileScript(descriptor, { id: 'module-notes-form', inlineTemplate: true });
const component = {};
const stub = vue.defineComponent({ setup: (_props, { attrs, slots }) => () => vue.h('div', attrs, slots.default?.()) });
vm.runInNewContext(ts.transpileModule(compiled.content, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, {
  exports: component, require(name) { if (name === 'vue') return vue; return { default: stub }; }
});
async function render(isModule) {
  const app = vue.createSSRApp(component.default, {
    isModule, commandTypeOptions: [{value: isModule ? 'ansible_module' : 'playbook', label:'type'}],
    modelValue: {commandType: isModule ? 'ansible_module' : 'playbook',content:'',moduleName:'ansible.builtin.service',moduleParamNotes:[{key:'name',value:'服务名称，如 nginx'}],defaultVars:'{}',argumentSchema:'',outputExtractors:'',remark:'',timeoutSeconds:60,becomeEnabled:false,checkModeSupported:false}
  });
  ['ElRadio','ElRadioGroup','ElFormItem','ElButton','ElInput','ElInputNumber','ElSwitch','ElCollapse','ElCollapseItem'].forEach(name => app.component(name, stub));
  app.component('ElTable', { props:['data'], setup(props, {slots}) { vue.provide('rows', props.data); return () => vue.h('div', slots.default?.()); } });
  app.component('ElTableColumn', { props:['label'], setup(props, {slots}) { const rows=vue.inject('rows',[]); return () => vue.h('div',[props.label,...rows.map((row,index) => slots.default?.({row,$index:index}))]); } });
  app.component('FormLabelHelp', { props:['label'], setup(props) { return () => vue.h('span',props.label); } });
  return renderToString(app);
}
test('Module renders user key-value notes without defaults, extra_vars or advanced controls', async () => {
  const html = await render(true);
  assert.match(html,/模块参数说明/);
  assert.match(html,/参数名（Key）/);
  assert.match(html,/参数说明（Value）/);
  assert.match(html,/服务名称，如 nginx/);
  assert.doesNotMatch(html,/默认模块参数|额外变量 extra_vars|高级配置|执行超时|模块参数参考/);
});
test('Playbook retains its own extra_vars and advanced controls', async () => {
  const html = await render(false);
  assert.match(html,/额外变量 extra_vars/);
  assert.match(html,/高级配置/);
  assert.doesNotMatch(html,/模块参数说明|添加参数说明/);
});
