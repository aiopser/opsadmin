const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const { requests, loadService } = require('./observability-api-contracts.cjs');

test('Monitoring API calls match the shared backend route contract', () => {
  const expected = JSON.parse(
    fs.readFileSync(path.join(__dirname, '../../docs/integrations/observability-api-contracts.json'), 'utf8')
  );
  assert.deepEqual(JSON.parse(JSON.stringify(requests())), expected);
});

test('JumpServer edit sends editable fields and preserves an intentionally blank secret', () => {
  const request = loadService('integrations').saveJumpServer(
    {
      id: 7,
      name: 'example',
      secret: '',
      has_secret: true,
      selected_host_ids: [1],
      sync_actor: 9
    },
    7
  );
  assert.equal(request.method, 'patch');
  assert.equal(request.data.secret, '');
  assert.equal(request.data.name, 'example');
  for (const field of ['id', 'has_secret', 'selected_host_ids', 'sync_actor']) {
    assert.equal(Object.hasOwn(request.data, field), false);
  }
});
