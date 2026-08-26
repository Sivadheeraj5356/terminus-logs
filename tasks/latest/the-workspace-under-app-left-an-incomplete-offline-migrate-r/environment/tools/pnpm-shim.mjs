#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, symlinkSync, rmSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { knitPlan } from './weave.mjs';
import { linkFrozen } from './emit.mjs';
import { contentDigestOf } from './hash.mjs';

const root = process.cwd();
const args = process.argv.slice(2);

function runNode(script) {
  const result = spawnSync(process.execPath, [script], { cwd: root, stdio: 'inherit' });
  process.exit(result.status ?? 1);
}

if (args[0] === 'run') {
  const pkg = JSON.parse(readFileSync(`${root}/package.json`, 'utf8'));
  const script = pkg.scripts?.[args[1]];
  if (!script) {
    console.error(`missing script ${args[1]}`);
    process.exit(1);
  }
  const env = { ...process.env, PATH: `${root}/tools:${process.env.PATH || ''}` };
  if (/^node\s+\S+$/.test(script.trim())) {
    const result = spawnSync(process.execPath, [script.trim().slice(5)], {
      cwd: root,
      stdio: 'inherit',
      env,
    });
    process.exit(result.status ?? 1);
  }
  const result = spawnSync(script, { cwd: root, stdio: 'inherit', shell: true, env });
  process.exit(result.status ?? 1);
}

if (args[0] === 'install') {
  const plan = knitPlan(root);
  const peerMap = plan.peerMap || new Map();
  for (const pkg of plan.packages) {
    const peers = peerMap.get(pkg.name) || [];
    pkg.contentDigest = contentDigestOf({
      name: pkg.name,
      version: pkg.version,
      path: pkg.path,
      peers,
      markers: { sealed: true },
    });
  }
  linkFrozen(root, plan);
  mkdirSync(`${root}/node_modules`, { recursive: true });
  console.log(JSON.stringify({ installed: true, importers: Object.keys(plan.importers) }));
  process.exit(0);
}

console.error(`unsupported pnpm args: ${args.join(' ')}`);
process.exit(1);
