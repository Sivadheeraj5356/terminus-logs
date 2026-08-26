import { createHash } from 'node:crypto';

export function sha256Text(text) {
  return createHash('sha256').update(String(text), 'utf8').digest('hex');
}

export function sha256Bytes(buf) {
  return createHash('sha256').update(buf).digest('hex');
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.keys(value).sort().reduce((acc, key) => {
      acc[key] = canonicalize(value[key]);
      return acc;
    }, {});
  }
  return value;
}

export function contentDigestOf(payload) {
  return sha256Text(JSON.stringify(canonicalize(payload)) + '\n');
}
