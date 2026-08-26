import fs from 'node:fs';
import path from 'node:path';

const FLAG = path.join('/app', '.forgekit_cache_reset');

export function markCacheReset() {
  fs.writeFileSync(FLAG, String(Date.now()));
}

export function cacheWasReset() {
  return fs.existsSync(FLAG);
}

export function isCacheResetPending() {
  return fs.existsSync(FLAG);
}

export function clearResetFlag() {
  if (fs.existsSync(FLAG)) fs.unlinkSync(FLAG);
}
