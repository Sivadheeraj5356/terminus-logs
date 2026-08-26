#!/usr/bin/env node
import path from 'node:path';
import { runCompile } from './entry.mjs';
import { runStatusSync } from './status_cmd.mjs';
import { markCacheReset } from '../passes/cache_reset.mjs';

const [, , cmd, ...rest] = process.argv;

function argValue(flag) {
  const idx = rest.indexOf(flag);
  if (idx === -1 || idx + 1 >= rest.length) return null;
  return rest[idx + 1];
}

async function main() {
  if (cmd === 'compile') {
    const spec = argValue('--spec');
    const out = argValue('--out');
    if (!spec || !out) {
      console.error('usage: driver.mjs compile --spec <path> --out <dir>');
      process.exit(2);
    }
    await runCompile(path.resolve(spec), path.resolve(out));
    return;
  }
  if (cmd === 'status') {
    const trace = argValue('--trace') ?? '/app/output/pass.trace.json';
    console.log(JSON.stringify(runStatusSync(trace)));
    return;
  }
  if (cmd === 'cache-reset') {
    markCacheReset();
    console.log('cache migration flag set');
    return;
  }
  console.error('unknown command');
  process.exit(2);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
