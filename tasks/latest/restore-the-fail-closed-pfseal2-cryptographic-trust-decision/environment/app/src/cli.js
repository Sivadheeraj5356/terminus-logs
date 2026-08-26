import path from 'node:path';
import { UsageError } from './errors.js';
import { normalizeTimestamp } from './time.js';

export const USAGE = 'Usage: pfseal-worker --db ABSOLUTE_PATH --worker-id ID [--once | --idle-limit N] [--poll-ms N] [--at RFC3339]';

function integer(name, raw, minimum, maximum) {
  if (!/^(0|[1-9]\d*)$/.test(raw ?? '')) throw new UsageError(`${name} must be an integer`);
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new UsageError(`${name} must be between ${minimum} and ${maximum}`);
  }
  return value;
}

export function parseArgs(argv, now = () => new Date().toISOString()) {
  if (argv.length === 1 && argv[0] === '--help') return { help: true };
  const out = { once: false, idleLimit: 0, pollMs: 1000 };
  const valued = new Set(['--db', '--worker-id', '--poll-ms', '--idle-limit', '--at']);
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--once') {
      if (out.once) throw new UsageError('duplicate --once');
      out.once = true;
      continue;
    }
    if (!valued.has(token)) throw new UsageError(`unknown option ${token}`);
    if (index + 1 >= argv.length || argv[index + 1].startsWith('--')) {
      throw new UsageError(`${token} requires a value`);
    }
    const key = token.slice(2);
    if (Object.hasOwn(out, key)) throw new UsageError(`duplicate ${token}`);
    out[key] = argv[index + 1];
    index += 1;
  }
  if (!out.db) throw new UsageError('--db is required');
  if (!path.isAbsolute(out.db)) throw new UsageError('--db must be an absolute path');
  if (!out['worker-id']) throw new UsageError('--worker-id is required');
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(out['worker-id'])) {
    throw new UsageError('--worker-id is invalid');
  }
  out.workerId = out['worker-id'];
  delete out['worker-id'];
  out.pollMs = integer('--poll-ms', String(out['poll-ms'] ?? out.pollMs), 10, 60000);
  delete out['poll-ms'];
  out.idleLimit = integer('--idle-limit', String(out['idle-limit'] ?? out.idleLimit), 0, 1000);
  delete out['idle-limit'];
  if (out.once && out.idleLimit !== 0) throw new UsageError('--once cannot be combined with --idle-limit');
  const at = out.at ?? now();
  out.at = normalizeTimestamp(at);
  if (!out.at) throw new UsageError('--at must be canonical UTC RFC3339 with milliseconds');
  return out;
}
