const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");

function loadFunctions(filename, names, bindings) {
  const source = fs
    .readFileSync(
      path.join(__dirname, "../src/views/monitoring", filename, "index.vue"),
      "utf8",
    )
    .match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const parsed = ts.createSourceFile(
    "page.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  const functions = parsed.statements.filter(
    (node) => ts.isFunctionDeclaration(node) && names.includes(node.name.text),
  );
  const context = { ...bindings };
  vm.runInNewContext(
    ts.transpileModule(
      functions.map((node) => node.getText(parsed)).join("\n"),
      { compilerOptions: { target: ts.ScriptTarget.ES2022 } },
    ).outputText,
    context,
  );
  return context;
}

function deferred() {
  let finish;
  const promise = new Promise((resolve) => {
    finish = resolve;
  });
  return { promise, finish };
}

test("Consul drawer ignores late response from a previously selected connection", async () => {
  const first = deferred();
  const second = deferred();
  const api = loadFunctions("consul", ["viewServices"], {
    serviceSequence: 0,
    selectedName: {},
    services: {},
    serviceError: {},
    servicesVisible: {},
    servicesLoading: {},
    getConsulServices: (id) => (id === 1 ? first.promise : second.promise),
  });
  const requestA = api.viewServices({ id: 1, name: "A" });
  const requestB = api.viewServices({ id: 2, name: "B" });
  second.finish({ data: ["B"], error: null });
  await requestB;
  first.finish({ data: ["A"], error: null });
  await requestA;
  assert.equal(api.selectedName.value, "B");
  assert.deepEqual(api.services.value, ["B"]);
});

test("Monitoring record drawer ignores a previous target response", async () => {
  const first = deferred();
  const second = deferred();
  const api = loadFunctions("targets", ["loadRecords"], {
    recordSequence: 0,
    disposed: false,
    selectedTarget: { value: { id: 1 } },
    recordsLoading: {},
    recordsPage: { value: 1 },
    records: {},
    recordsTotal: {},
    getMonitoringRecords: (id) => (id === 1 ? first.promise : second.promise),
  });
  const requestA = api.loadRecords();
  api.selectedTarget.value = { id: 2 };
  const requestB = api.loadRecords();
  second.finish({ data: { list: ["B"], total: 1 }, error: null });
  await requestB;
  first.finish({ data: { list: ["A"], total: 100 }, error: null });
  await requestA;
  assert.deepEqual(api.records.value, ["B"]);
  assert.equal(api.recordsTotal.value, 1);
});

test("Monitoring Meta editor rejects arrays and non-string values", () => {
  const api = loadFunctions("targets", ["parseMeta"], {
    metaText: { value: "[1]" },
    metaError: {},
  });
  assert.equal(api.parseMeta(), undefined);
  api.metaText.value = '{"team":123}';
  assert.equal(api.parseMeta(), undefined);
  api.metaText.value = '{"team":"ops"}';
  assert.equal(api.parseMeta().team, "ops");
});
