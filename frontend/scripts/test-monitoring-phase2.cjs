const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");

function functions(filename, names, bindings) {
  const source = fs
    .readFileSync(
      path.join(__dirname, "../src/views/monitoring", filename),
      "utf8",
    )
    .match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
  const ast = ts.createSourceFile(
    "page.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
  );
  const selected = ast.statements.filter(
    (node) => ts.isFunctionDeclaration(node) && names.includes(node.name.text),
  );
  const context = { ...bindings };
  vm.runInNewContext(
    ts.transpileModule(selected.map((node) => node.getText(ast)).join("\n"), {
      compilerOptions: { target: ts.ScriptTarget.ES2022 },
    }).outputText,
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

test("host import does not accept an old preview after its connection changed", async () => {
  const response = deferred();
  const api = functions(
    "targets/modules/host-import-drawer.vue",
    ["readPreview", "buildInput", "validNumericConfig"],
    {
      sequence: 0,
      props: { visible: true },
      connectionId: { value: 1 },
      selectedHosts: { value: [{ id: 1 }] },
      addressSource: { value: "internal" },
      port: { value: 9100 },
      interval: { value: 0 },
      followAddress: { value: false },
      loading: {},
      preview: {},
      confirmedInput: {},
      step: { value: 0 },
      page: {},
      window: { $message: { warning() {} } },
      previewHostImport: () => response.promise,
    },
  );
  const request = api.readPreview();
  api.connectionId.value = 2;
  response.finish({
    data: { create_count: 1, preview_token: "proof" },
    error: null,
  });
  await request;
  assert.equal(api.step.value, 0);
  assert.equal(api.confirmedInput.value, undefined);
});

test("Catalog ignores a previous data center or service instance response", async () => {
  const first = deferred();
  const second = deferred();
  const api = functions(
    "consul/modules/catalog-drawer.vue",
    ["loadInstances"],
    {
      sequence: 0,
      props: { visible: true, connection: { id: 1 } },
      service: { value: "A" },
      datacenter: { value: "dc1" },
      page: { value: 1 },
      instances: {},
      total: {},
      errorMessage: {},
      loading: {},
      getCatalogInstances: (_connection, query) =>
        query.service === "A" ? first.promise : second.promise,
    },
  );
  const requestA = api.loadInstances();
  api.datacenter.value = "dc2";
  api.service.value = "B";
  const requestB = api.loadInstances();
  second.finish({ data: { list: ["B"], total: 1 }, error: null });
  await requestB;
  first.finish({ data: { list: ["A"], total: 100 }, error: null });
  await requestA;
  assert.deepEqual(api.instances.value, ["B"]);
  assert.equal(api.total.value, 1);
});

test("host import confirmation prevents double submission", async () => {
  const response = deferred();
  let calls = 0;
  const api = functions("targets/modules/host-import-drawer.vue", ["confirm"], {
    saving: { value: false },
    confirmedInput: { value: { connection: 1, host_ids: [1] } },
    preview: { value: { create_count: 1, preview_token: "proof" } },
    window: { $message: { success() {}, warning() {} } },
    emit() {},
    commitHostImport: () => {
      calls += 1;
      return response.promise;
    },
  });
  const first = api.confirm();
  await api.confirm();
  assert.equal(calls, 1);
  response.finish({
    data: { created: 1, skipped: 0, delivery_failed: 0 },
    error: null,
  });
  await first;
  assert.equal(api.saving.value, false);
});
