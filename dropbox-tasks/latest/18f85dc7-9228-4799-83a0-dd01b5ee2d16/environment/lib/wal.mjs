import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const WAL_FILE = '/app/output/.cache/wal_segment.json';

function loadSegments() {
  if (!existsSync(WAL_FILE)) {
    return [];
  }
  try {
    const parsed = JSON.parse(readFileSync(WAL_FILE, 'utf8'));
    return Array.isArray(parsed.segments) ? parsed.segments : [];
  } catch {
    return [];
  }
}

function saveSegments(segments) {
  writeFileSync(WAL_FILE, JSON.stringify({ segments }));
}

export function appendTransition(priorEpoch, nextEpoch) {
  const segments = loadSegments();
  const seq = segments.length ? segments[segments.length - 1].seq + 1 : 1;
  segments.push({ seq, prior_epoch: priorEpoch, next_epoch: nextEpoch });
  saveSegments(segments);
  return nextEpoch;
}

export function reconcileEpoch(journalEpoch) {
  const segments = loadSegments();
  if (!segments.length) {
    return journalEpoch;
  }
  const tail = segments[segments.length - 1];
  return tail.prior_epoch;
}

export function latestTransition() {
  const segments = loadSegments();
  if (!segments.length) {
    return null;
  }
  return segments[segments.length - 1];
}

export function clearSegments() {
  saveSegments([]);
}

export function segmentCount() {
  return loadSegments().length;
}
