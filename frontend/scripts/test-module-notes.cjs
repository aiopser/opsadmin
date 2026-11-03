const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const exportsObject = {};
const source = fs.readFileSync(path.join(__dirname, '../src/constants/ansible-module-param-docs.ts'), 'utf8');
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports: exportsObject });
const rows = [{ key: 'name', value: '服务名称，例如 nginx' }, { key: 'state', value: '目标状态：started / stopped' }];
const schema = exportsObject.buildModuleNotes(rows);
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readModuleNotes(schema))), rows);
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.schemaToParamDocs(schema))), rows.map(row => ({ name: row.key, description: row.value })));
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readModuleNotes({ properties: { name: { type: 'string', description: '历史说明' } } }))), [{ key: 'name', value: '历史说明' }]);
assert.throws(() => exportsObject.buildModuleNotes([{ key: 'name', value: 'a' }, { key: ' name ', value: 'b' }]));
assert.throws(() => exportsObject.buildModuleNotes([{ key: 'name', value: '' }]));
assert.throws(() => exportsObject.buildModuleNotes([{ key: '', value: 'missing name' }]));
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.resolveModuleParamDocs(exportsObject.buildModuleNotes([]), 'ansible.builtin.service'))), []);
console.log('user maintained module key-value descriptions roundtrip and validation passed');

const historicalFlat = { name: { type: 'string', description: '服务名称' }, state: { description: '目标状态', choices: ['started', 'stopped'] } };
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readModuleNotes(historicalFlat))), [{key:'name',value:'服务名称'},{key:'state',value:'目标状态'}]);
const apiRoundtrip = JSON.parse(JSON.stringify({ argumentSchema: schema }));
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readModuleNotes(apiRoundtrip.argumentSchema))), rows);

const explicitVersion = {parameterDocs: exportsObject.buildParameterDocs(rows), argumentSchema: {properties:{wrong:{description:'old'}}}};
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readVersionModuleNotes(explicitVersion))), rows);
assert.deepEqual(JSON.parse(JSON.stringify(exportsObject.readVersionModuleNotes({parameterDocs:[],argumentSchema:historicalFlat}))), []);
