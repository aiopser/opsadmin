const fs = require('node:fs');
const process = require('node:process');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const samples = {
  monitoring: {
    getConsulConnections: [],
    saveConsulConnection: [undefined, {}],
    deleteConsulConnection: [7],
    testConsulConnection: [7],
    getConsulServices: [7],
    getMonitoringTargets: [2, 'example'],
    saveMonitoringTarget: [undefined, {}],
    deleteMonitoringTarget: [7],
    previewMonitoringTarget: [7],
    syncMonitoringTarget: [7, 'sync'],
    getMonitoringRecords: [7, 2],
    getPrometheusConfig: [7],
    getMonitoringAlertRules: [7],
    getConsulDatacenters: [7],
    getCatalogServices: [7, 'dc1'],
    getCatalogInstances: [7, { datacenter: 'dc1', service: 'node', page: 2 }],
    previewHostImport: [{}],
    commitHostImport: [{ preview_token: 'synthetic' }],
    getConsulKvKeys: [7, 'example/'],
    getConsulKvValue: [7, 'example/key'],
    updateConsulKv: [7, 'example/key', 'synthetic'],
    deleteConsulKv: [7, 'example/key'],
    getConsulTemplates: [],
    saveConsulTemplate: [undefined, {}],
    deleteConsulTemplate: [7],
    deployConsulTemplate: [7, '00000000-0000-0000-0000-000000000001'],
    requestConsulRemoteRead: [{ host: 7, path: '/etc/consul-template/config/app.hcl' }],
    getConsulRemoteRead: ['00000000-0000-0000-0000-000000000001'],
    compareConsulRemoteRead: ['00000000-0000-0000-0000-000000000001', 'synthetic']
  },
  enrollment: {
    getEnrollmentPolicies: [2, 'example'],
    saveEnrollmentPolicy: [undefined, {}],
    deleteEnrollmentPolicy: [7],
    previewEnrollmentPolicy: [7],
    confirmEnrollmentPolicy: [7, { preview_token: 'synthetic', operation: 'run' }],
    pauseEnrollmentPolicy: [7],
    getEnrollmentRuns: [7, 2]
  },
  integrations: {
    fetchJumpServers: ['example'],
    saveJumpServer: [{}, undefined],
    deleteJumpServer: [7],
    testJumpServer: [7],
    previewJumpServer: [7, [1, 2]],
    confirmJumpServer: [7, 8],
    fetchJumpServerRecords: [7]
  },
  security: {
    getSecuritySubscriptions: [],
    saveSecuritySubscription: [{}, undefined],
    collectSecuritySubscription: [7],
    getSecurityAdvisories: [{ page: 2, pageSize: 10, sortBy: 'published', order: 'desc' }],
    getSecurityCollections: []
  }
};

function loadService(name) {
  const filename = path.join(__dirname, '../src/service/api', `${name}.ts`);
  const source = fs.readFileSync(filename, 'utf8');
  const context = {
    exports: {},
    require: id => {
      if (id !== '../request') throw new Error(`Unexpected dependency: ${id}`);
      return { request: config => ({ method: 'get', ...config }) };
    }
  };
  vm.runInNewContext(
    ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
    }).outputText,
    context
  );
  return context.exports;
}

function requests() {
  return Object.entries(samples).flatMap(([service, calls]) => {
    const api = loadService(service);
    const missing = Object.keys(api).filter(name => typeof api[name] === 'function' && !(name in calls));
    if (missing.length) throw new Error(`Missing contract samples: ${service}/${missing.join(',')}`);
    const variants = [
      ...Object.entries(calls),
      ...(service === 'monitoring'
        ? [
            ['saveConsulConnection', [7, {}]],
            ['saveMonitoringTarget', [7, {}]],
            ['saveConsulTemplate', [7, {}]],
            ['syncMonitoringTarget', [7, 'deregister']]
          ]
        : []),
      ...(service === 'enrollment'
        ? [
            ['saveEnrollmentPolicy', [7, {}]],
            ['confirmEnrollmentPolicy', [7, { preview_token: 'synthetic', operation: 'enable' }]]
          ]
        : []),
      ...(service === 'integrations' ? [['saveJumpServer', [{}, 7]]] : []),
      ...(service === 'security' ? [['saveSecuritySubscription', [{}, 7]]] : [])
    ];
    return variants.map(([name, args]) => ({ service, name, ...api[name](...args) }));
  });
}

module.exports = { requests, loadService };
if (require.main === module) {
  const output = `${JSON.stringify(requests(), null, 2)}\n`;
  if (process.argv.includes('--write')) {
    fs.writeFileSync(path.join(__dirname, '../../docs/integrations/observability-api-contracts.json'), output, 'utf8');
  } else {
    process.stdout.write(output);
  }
}
