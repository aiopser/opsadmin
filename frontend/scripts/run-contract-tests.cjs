const { spawnSync } = require('node:child_process');
const { readdirSync } = require('node:fs');
const path = require('node:path');

// Expand the test list in Node so PowerShell and Unix shells run the same files.
const testFiles = readdirSync(__dirname)
  .filter(filename => /^test-.*\.cjs$/.test(filename))
  .sort()
  .map(filename => path.join(__dirname, filename));

if (testFiles.length === 0) {
  throw new Error('No frontend contract scripts were found');
}

const result = spawnSync(process.execPath, ['--test', ...testFiles], {
  cwd: path.resolve(__dirname, '..'),
  stdio: 'inherit'
});

if (result.error) {
  throw result.error;
}

process.exitCode = result.status ?? 1;
