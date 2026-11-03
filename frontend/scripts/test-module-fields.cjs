const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const {test} = require('node:test');
const notes = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/constants/ansible-module-param-docs.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:notes});
function functions(relative, names, bindings) {
 const source=fs.readFileSync(path.join(__dirname,relative),'utf8').match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
 const parsed=ts.createSourceFile('editor.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const selected=parsed.statements.filter(node=>ts.isFunctionDeclaration(node)&&names.includes(node.name.text));
 const context={...bindings};
 vm.runInNewContext(ts.transpileModule(selected.map(node=>node.getText(parsed)).join('\n'),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText,context);
 return context;
}
test('Module payload writes moduleName and parameterDocs, leaving content and schema empty',()=>{
 const api=functions('../src/views/automation/resources/modules/command-page.vue',['buildVersionPayload','parseJsonArray','parseJsonObject'],{props:{resourceKind:'module'},buildParameterDocs:notes.buildParameterDocs,window:{$message:{error(){}}}});
 const payload=api.buildVersionPayload({commandType:'ansible_module',moduleName:'ansible.builtin.service',content:'legacy-name',moduleParamNotes:[{key:'name',value:'服务名称'}],argumentSchema:'{"old":{}}',defaultVars:'{"hidden":1}',outputExtractors:'[]',remark:'',timeoutSeconds:90,becomeEnabled:true,checkModeSupported:true});
 assert.equal(payload.moduleName,'ansible.builtin.service');
 assert.equal(payload.content,'');
 assert.deepEqual(JSON.parse(JSON.stringify(payload.parameterDocs)),[{name:'name',description:'服务名称'}]);
 assert.deepEqual(JSON.parse(JSON.stringify(payload.argumentSchema)),{});
 assert.deepEqual(JSON.parse(JSON.stringify(payload.defaultVars)),{});
});
test('Module notes use explicit DTO fields; an explicit empty array never restores legacy schema notes',()=>{
 assert.deepEqual(JSON.parse(JSON.stringify(notes.readVersionModuleNotes({parameterDocs:[{name:'name',description:'服务名'}],argumentSchema:{properties:{wrong:{description:'old'}}}}))),[{key:'name',value:'服务名'}]);
 assert.deepEqual(JSON.parse(JSON.stringify(notes.readVersionModuleNotes({parameterDocs:[],argumentSchema:{properties:{wrong:{description:'old'}}}}))),[]);
});
test('Migration-era versions keep legacy defaults, new explicit versions do not',()=>{
 const api=functions('../src/views/ops/quick-execute/module/index.vue',['versionDefaultArgs'],{});
 assert.equal(api.versionDefaultArgs({moduleName:'ansible.builtin.service',content:'',parameterDocs:[],defaultVars:{module_args:{name:'hidden'}}}), '');
 assert.deepEqual(JSON.parse(api.versionDefaultArgs({moduleName:'ansible.builtin.service',content:'ansible.builtin.service',defaultVars:{module_args:{name:'nginx'}}})),{name:'nginx'});
});
