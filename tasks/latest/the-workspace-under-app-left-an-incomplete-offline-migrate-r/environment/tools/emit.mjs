import { readFileSync, writeFileSync, mkdirSync, symlinkSync, rmSync, existsSync } from 'node:fs';
import { dirname, relative } from 'node:path';
import { writeJson } from './json.mjs';

export function writePlanGraph(root, plan) {
  const packages = plan.packages.map((pkg) => ({
    name: pkg.name,
    version: pkg.version,
    path: pkg.path,
    contentDigest: pkg.contentDigest,
  }));
  writeJson(`${root}/generated/plan-graph.json`, {
    schema: 'migrate-plan-graph-v1',
    train: plan.train.id,
    epoch: plan.train.epoch,
    importers: plan.importers,
    peers: plan.peers,
    fingerprint: plan.fingerprint,
    packages,
  });
}

export function writeLockAndManifests(root, plan) {
  const lines = ["lockfileVersion: '9.0'", 'importers:'];
  lines.push('  .:');
  lines.push('    dependencies: {}');
  for (const importer of Object.keys(plan.importers).sort()) {
    lines.push(`  ${importer}:`);
    lines.push('    dependencies:');
    const edges = plan.importers[importer];
    for (const alias of Object.keys(edges).sort()) {
      const spec = edges[alias];
      const target = spec.slice('workspace:'.length).split('@*')[0];
      const pkg = plan.packages.find((item) => item.name === target);
      const rel = relative(importer, pkg.path).replaceAll('\\', '/');
      lines.push(`      '${alias}':`);
      lines.push(`        specifier: ${spec}`);
      lines.push(`        version: link:${rel}`);
    }
  }
  lines.push('packages: {}');
  writeFileSync(`${root}/pnpm-lock.yaml`, lines.join('\n') + '\n');

  for (const importer of Object.keys(plan.importers)) {
    const manifestPath = `${root}/${importer}/package.json`;
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    manifest.dependencies = { ...plan.importers[importer] };
    writeJson(manifestPath, manifest);
  }
}

export function linkFrozen(root, plan) {
  for (const importer of Object.keys(plan.importers)) {
    const nm = `${root}/${importer}/node_modules`;
    rmSync(nm, { recursive: true, force: true });
    mkdirSync(nm, { recursive: true });
    for (const [alias, spec] of Object.entries(plan.importers[importer])) {
      const target = spec.slice('workspace:'.length).split('@*')[0];
      const pkg = plan.packages.find((item) => item.name === target);
      const dest = `${nm}/${alias}`;
      mkdirSync(dirname(dest), { recursive: true });
      if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
      symlinkSync(`${root}/${pkg.path}`, dest);
    }
  }
}
