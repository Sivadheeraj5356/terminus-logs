import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import {
  readGeneration,
  writeGeneration,
  onMigration,
  truncateEntries,
} from './replay_log.mjs';
import { appendTransition, reconcileEpoch, clearSegments } from './wal.mjs';

const JOURNAL_FILE = '/app/output/.cache/compile_journal.json';

export function readEpoch() {
  if (!existsSync(JOURNAL_FILE)) {
    return readGeneration();
  }
  try {
    const data = JSON.parse(readFileSync(JOURNAL_FILE, 'utf8'));
    const stored = data.epoch ?? readGeneration();
    return reconcileEpoch(stored);
  } catch {
    return readGeneration();
  }
}

export function writeEpoch(epoch) {
  writeFileSync(JOURNAL_FILE, JSON.stringify({ epoch }));
  writeGeneration(epoch);
}

export function ensureEpoch() {
  const current = readEpoch();
  if (current === 0) {
    writeEpoch(1);
    return 1;
  }
  return current;
}

export function onCacheReset() {
  const current = readEpoch();
  appendTransition(current, current + 1);
  const migrated = onMigration();
  truncateEntries();
  writeEpoch(migrated);
  return migrated;
}

export function finalizeMigrationEpoch() {
  clearSegments();
}
