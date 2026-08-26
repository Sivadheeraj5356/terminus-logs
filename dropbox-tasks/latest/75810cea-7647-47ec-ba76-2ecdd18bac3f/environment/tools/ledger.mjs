import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export function readLedger(path) {
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

export function writeLedger(path, events) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, events.map((e) => JSON.stringify(e)).join('\n') + (events.length ? '\n' : ''));
}

export function appendLedger(path, event) {
  const events = readLedger(path);
  events.push(event);
  writeLedger(path, events);
}

export function lastCommitIndex(events) {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].phase === 'COMMIT') return i;
  }
  return -1;
}
