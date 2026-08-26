import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const REPLAY_FILE = '/app/output/.cache/replay_log.json';

function loadLog() {
  if (!existsSync(REPLAY_FILE)) {
    return { generation: 0, entries: [] };
  }
  try {
    return JSON.parse(readFileSync(REPLAY_FILE, 'utf8'));
  } catch {
    return { generation: 0, entries: [] };
  }
}

function saveLog(data) {
  writeFileSync(REPLAY_FILE, JSON.stringify(data));
}

export function readGeneration() {
  return loadLog().generation;
}

export function writeGeneration(gen) {
  const log = loadLog();
  log.generation = gen;
  saveLog(log);
}

export function countEntriesForGeneration(gen) {
  const log = loadLog();
  return log.entries.filter((entry) => entry.generation === gen).length;
}

export function recordEntry(packCount, digest) {
  const log = loadLog();
  const gen = log.generation > 0 ? log.generation - 1 : 0;
  log.entries.push({ generation: gen, packCount, digest, ts: Date.now() });
  saveLog(log);
}

export function lastEntryDigest() {
  const log = loadLog();
  if (!log.entries.length) return null;
  return log.entries[log.entries.length - 1].digest;
}

export function onMigration() {
  const log = loadLog();
  return log.generation;
}

export function truncateEntries() {
  const log = loadLog();
  log.entries = [];
  saveLog(log);
}

export function entriesForGeneration(gen) {
  const log = loadLog();
  return log.entries.filter((entry) => entry.generation === gen);
}
