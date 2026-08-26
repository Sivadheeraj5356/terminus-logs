import { mkdirSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { readJson, writeJson } from './json.mjs';
import { contentDigestOf, sha256Bytes } from './hash.mjs';

function tarballName(pkg) {
  return `${pkg.path.split('/').pop()}-${pkg.version}.json`;
}

export function fillCask(root, plan) {
  mkdirSync(`${root}/offline-store/tarballs`, { recursive: true });
  const prev = existsSync(`${root}/offline-store/index.json`)
    ? readJson(`${root}/offline-store/index.json`)
    : { schema: 'migrate-store-index-v1', packages: {} };
  const next = { ...(prev.packages || {}) };
  for (const pkg of plan.packages) {
    const payload = {
      name: pkg.name,
      version: pkg.version,
      path: pkg.path,
      markers: { sealed: true },
    };
    const digest = contentDigestOf(payload);
    const body = Buffer.from(JSON.stringify(payload, null, 2) + String.fromCharCode(10));
    const rel = `offline-store/tarballs/${tarballName(pkg)}`;
    writeFileSync(`${root}/${rel}`, body);
    const key = `${pkg.name}@${pkg.version}#${digest.slice(0, 16)}`;
    next[key] = {
      name: pkg.name,
      version: pkg.version,
      path: pkg.path,
      tarball: rel,
      sha256: sha256Bytes(body),
      bytes: body.length,
      contentDigest: digest,
    };
  }
  const index = { schema: 'migrate-store-index-v1', packages: next };
  writeJson(`${root}/offline-store/index.json`, index);
  return index;
}
