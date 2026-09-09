const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const vue = require('vue');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/hooks/business/run-event-stream.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
}).outputText;
const flush = () =>
  new Promise(resolve => {
    setImmediate(resolve);
  });
const page = (sequence, more = false, terminal = false) => ({
  error: null,
  data: { events: [{ id: sequence, sequence }], nextCursor: sequence, hasMore: more, terminal }
});

function harness(fetchPage) {
  const timers = new Map();
  const calls = [];
  const exported = {};
  const context = {
    exports: exported,
    AbortController,
    setTimeout: (fn, delay) => {
      timers.set(fn, delay);
      return fn;
    },
    clearTimeout: fn => timers.delete(fn),
    require: name => {
      if (name === 'vue') return vue;
      if (name === '@/service/api')
        return {
          fetchGetRunEvents: (...args) => {
            calls.push(args);
            return fetchPage(...args);
          },
          fetchRealtimeTicket: async () => ({ error: { message: 'isolated Redis unavailable' }, data: null }),
          runEventWebSocketUrl: () => {
            throw new Error('No external transport permitted');
          }
        };
      throw new Error(`Unexpected dependency ${name}`);
    }
  };
  vm.runInNewContext(compiled, context);
  const id = vue.ref(1);
  const domain = vue.ref('ops');
  const scope = vue.effectScope();
  const stream = scope.run(() => exported.useRunEventStream(id, domain));
  return {
    id,
    domain,
    stream,
    calls,
    stop: () => scope.stop(),
    tick: delay => {
      [...timers]
        .filter(([, ms]) => ms === delay)
        .forEach(([fn]) => {
          timers.delete(fn);
          fn();
        });
    },
    timers
  };
}

test('drains more than twenty terminal pages before stopping', async () => {
  const h = harness(async (_id, cursor) => page(cursor + 1, cursor < 24, true));
  await flush();
  assert.equal(h.stream.events.value.length, 25);
  assert.equal(h.stream.terminal.value, true);
  assert.equal(h.calls.length, 25);
  assert.equal(h.calls[0][2].domain, 'ops');
  assert.equal(h.timers.size, 0);
  h.stop();
});

test('terminal pagination failure retries without marking the tail complete', async () => {
  let requests = 0;
  const h = harness(async () => {
    requests += 1;
    if (requests === 1) return page(1, true, true);
    if (requests === 2) return { data: null, error: { message: 'offline' } };
    return page(2, false, true);
  });
  await flush();
  assert.equal(h.stream.terminal.value, false);
  h.tick(5000);
  await flush();
  assert.equal(h.stream.terminal.value, true);
  assert.deepEqual(
    Array.from(h.stream.events.value, item => item.sequence),
    [1, 2]
  );
  h.stop();
});

test('switching A to B to A aborts and rejects the old A response', async () => {
  let completeOld;
  let first = true;
  const h = harness(async () => {
    if (first) {
      first = false;
      return new Promise(resolve => {
        completeOld = resolve;
      });
    }
    return page(2, false, true);
  });
  const oldSignal = h.calls[0][2].signal;
  h.id.value = 2;
  await vue.nextTick();
  h.id.value = 1;
  await vue.nextTick();
  await flush();
  completeOld(page(999, false, true));
  await flush();
  assert.equal(oldSignal.aborted, true);
  assert.deepEqual(
    Array.from(h.stream.events.value, item => item.sequence),
    [2]
  );
  h.stop();
});

test('disposal cancels in-flight requests and prevents writes', async () => {
  let complete;
  const h = harness(
    () =>
      new Promise(resolve => {
        complete = resolve;
      })
  );
  h.stop();
  complete(page(1, false, true));
  await flush();
  assert.equal(h.calls[0][2].signal.aborted, true);
  assert.equal(h.stream.events.value.length, 0);
  assert.equal(h.timers.size, 0);
});
