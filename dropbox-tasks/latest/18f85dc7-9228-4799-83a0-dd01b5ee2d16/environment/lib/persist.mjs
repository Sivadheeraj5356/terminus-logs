import { createHash } from 'node:crypto';
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  rmSync,
  readdirSync,
  unlinkSync,
} from 'node:fs';
import { join } from 'node:path';

const CACHE_DIR = '/app/output/.cache';

export function ensureCache() {
  if (!existsSync(CACHE_DIR)) {
    mkdirSync(CACHE_DIR, { recursive: true });
  }
}

export function clearCache() {
  if (!existsSync(CACHE_DIR)) {
    mkdirSync(CACHE_DIR, { recursive: true });
    return;
  }
  for (const name of readdirSync(CACHE_DIR)) {
    if (
      name.startsWith('stage_two')
      || name.startsWith('.stage_two')
      || name === 'compile_journal.json'
      || name === 'replay_log.json'
      || name === 'wal_segment.json'
    ) {
      continue;
    }
    unlinkSync(join(CACHE_DIR, name));
  }
}

export function cachePath(key) {
  return join(CACHE_DIR, `${key}.json`);
}

export function hashInputs(inputs) {
  const hash = createHash('sha256');
  for (const input of inputs) {
    if (typeof input === 'string') {
      hash.update(input);
    } else if (Buffer.isBuffer(input)) {
      hash.update(input);
    } else {
      hash.update(JSON.stringify(input));
    }
  }
  return hash.digest('hex').slice(0, 16);
}

export function readCache(key) {
  const path = cachePath(key);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return null;
  }
}

export function writeCache(key, data, deps) {
  ensureCache();
  const entry = {
    data,
    deps: deps || [],
    timestamp: Date.now(),
  };
  writeFileSync(cachePath(key), JSON.stringify(entry));
  return entry;
}

export function invalidateStale(cacheKey, currentHash) {
  const cached = readCache(cacheKey);
  if (!cached) return true;
  const age = Date.now() - (cached.timestamp || 0);
  return age > 1000 * 60 * 60 * 24;
}

export function getDepHash(depKey) {
  const cached = readCache(depKey);
  if (!cached) return null;
  return cached.timestamp ? String(cached.timestamp) : null;
}
