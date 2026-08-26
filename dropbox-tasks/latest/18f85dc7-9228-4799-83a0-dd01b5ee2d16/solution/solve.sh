#!/usr/bin/env bash
set -euo pipefail

FK=/app/environment

python3 <<'PY'
from pathlib import Path
replay = Path('/app/environment/lib/replay_log.mjs')
text = replay.read_text()
text = text.replace(
    '  const gen = log.generation > 0 ? log.generation - 1 : 0;\n'
    '  log.entries.push({ generation: gen, packCount, digest, ts: Date.now() });',
    '  log.entries.push({ generation: log.generation, packCount, digest, ts: Date.now() });',
)
replay.write_text(text)
PY

python3 <<'PY'
from pathlib import Path
wal = Path('/app/environment/lib/wal.mjs')
text = wal.read_text()
text = text.replace(
    '  return tail.prior_epoch;',
    '  return Math.max(journalEpoch, tail.next_epoch);',
)
wal.write_text(text)
PY

cat > "$FK/lib/journal.mjs" <<'EOF'
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import {
  readGeneration,
  writeGeneration,
  truncateEntries,
} from './replay_log.mjs';
import { appendTransition, reconcileEpoch, clearSegments } from './wal.mjs';

const JOURNAL_FILE = '/app/output/.cache/compile_journal.json';

function readStoredEpoch() {
  if (!existsSync(JOURNAL_FILE)) {
    return readGeneration();
  }
  try {
    const data = JSON.parse(readFileSync(JOURNAL_FILE, 'utf8'));
    return data.epoch ?? readGeneration();
  } catch {
    return readGeneration();
  }
}

export function readEpoch() {
  const stored = readStoredEpoch();
  const reconciled = reconcileEpoch(stored);
  if (reconciled !== stored) {
    writeEpoch(reconciled);
    return reconciled;
  }
  return stored;
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
  const prior = readStoredEpoch();
  const next = prior + 1;
  appendTransition(prior, next);
  truncateEntries();
  writeEpoch(next);
  return next;
}

export function finalizeMigrationEpoch() {
  clearSegments();
}
EOF

cat > "$FK/lib/persist.mjs" <<'EOF'
import { createHash } from 'node:crypto';
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  unlinkSync,
  renameSync,
} from 'node:fs';
import { join } from 'node:path';

const CACHE_DIR = '/app/output/.cache';

export function ensureCache() {
  if (!existsSync(CACHE_DIR)) {
    mkdirSync(CACHE_DIR, { recursive: true });
  }
}

export function clearCache() {
  ensureCache();
  if (!existsSync(CACHE_DIR)) {
    mkdirSync(CACHE_DIR, { recursive: true });
    return;
  }
  for (const name of readdirSync(CACHE_DIR)) {
    if (
      name === 'compile_journal.json'
      || name === 'replay_log.json'
      || name === 'wal_segment.json'
    ) {
      continue;
    }
    const target = join(CACHE_DIR, name);
    if (name.startsWith('.') && name.endsWith('.tmp')) {
      unlinkSync(target);
      continue;
    }
    if (target.endsWith('.json')) {
      unlinkSync(target);
    }
  }
}

export function cachePath(key) {
  return join(CACHE_DIR, `${key}.json`);
}

export function cacheTempPath(key) {
  return join(CACHE_DIR, `.${key}.tmp`);
}

export function hashInputs(inputs) {
  const hash = createHash('sha256');
  for (const input of inputs) {
    if (typeof input === 'string') {
      hash.update(input);
    } else if (Buffer.isBuffer(input)) {
      hash.update(input);
    } else {
      hash.update(JSON.stringify(input, Object.keys(input).sort()));
    }
  }
  return hash.digest('hex').slice(0, 16);
}

export function depsSatisfied(deps) {
  if (!deps || !deps.length) {
    return true;
  }
  for (const dep of deps) {
    if (!readCache(dep)) {
      return false;
    }
  }
  return true;
}

export function readCache(key) {
  const path = cachePath(key);
  if (!existsSync(path)) return null;
  try {
    const data = JSON.parse(readFileSync(path, 'utf8'));
    if (data.deps && !depsSatisfied(data.deps)) {
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

export function writeCache(key, data, deps) {
  ensureCache();
  const entry = {
    data,
    deps: deps || [],
    content_hash: hashInputs([JSON.stringify(data)]),
  };
  const tempPath = cacheTempPath(key);
  const finalPath = cachePath(key);
  writeFileSync(tempPath, JSON.stringify(entry));
  renameSync(tempPath, finalPath);
  return entry;
}

export function invalidateStale(cacheKey, contentHash) {
  const cached = readCache(cacheKey);
  if (!cached) return true;
  return cached.content_hash !== contentHash;
}

export function getDepHash(depKey) {
  const cached = readCache(depKey);
  if (!cached) return null;
  return cached.content_hash;
}

export function describeCacheEntry(key) {
  const cached = readCache(key);
  if (!cached) {
    return { present: false, key };
  }
  return {
    present: true,
    key,
    dep_count: (cached.deps || []).length,
    content_hash: cached.content_hash || null,
  };
}
EOF

cat > "$FK/cli/entry.mjs" <<'EOF'
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadPack } from '../ir/pack.mjs';
import { loadGrid } from '../ir/lattice.mjs';
import { runPhaseA } from '../pipeline/phase_a.mjs';
import { runStageTwo } from '../pipeline/stage_two.mjs';
import { buildMetrics, traceTail } from '../pipeline/stage_three.mjs';
import { kernelTemplate, writeKernel } from '../emit/kernel_writer.mjs';
import { clearResetFlag, isCacheResetPending } from '../passes/cache_reset.mjs';
import { ensureCache, readCache, writeCache, hashInputs, invalidateStale, clearCache } from '../lib/persist.mjs';
import { ensureEpoch, onCacheReset, readEpoch, writeEpoch, finalizeMigrationEpoch } from '../lib/journal.mjs';
import { recordEntry } from '../lib/replay_log.mjs';
import { canonJson } from '../lib/canon_json.mjs';
import { sha256Hex } from '../lib/hash_util.mjs';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const FORGE_ROOT = path.resolve(ROOT, '..');

function readJsonAt(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function computePackKey(pack, grid, ghost) {
  const inputs = [
    pack.id,
    pack.spill_budget,
    pack.scratch_cap_bytes,
    pack.temporal_tiling,
    JSON.stringify(pack.tile),
    grid.nx, grid.ny, grid.nz,
    ghost,
  ];
  return `pack:${pack.id}:${hashInputs(inputs)}`;
}

function computePhaseAKey(packKey) {
  return `phase_a:${packKey}`;
}

function computeStageTwoKey(packKey, edgeInfo) {
  const edgeHash = hashInputs([edgeInfo.edge_mode, edgeInfo.peel_rows]);
  return `stage_two:${packKey}:${edgeHash}`;
}

function computeDigestKey(traceKey, kernelHash) {
  return `digest:${traceKey}:${kernelHash}`;
}

function packRecordFromStages(pack, tileInfo, edgeInfo, laneInfo, tallied, divisors) {
  return {
    pack_id: pack.id,
    tile: tileInfo.tile,
    scratch_peak: tileInfo.scratch_peak,
    edge_mode: edgeInfo.edge_mode,
    peel_rows: edgeInfo.peel_rows,
    lane_width: laneInfo.lane_width,
    divisors,
    spill_total: tallied.spill_total,
  };
}

function spillWithinBudget(record, budget) {
  return record.spill_total <= budget;
}

function computeTraceHash(records) {
  return hashInputs(records.map((record) => JSON.stringify(record)));
}

function computeTraceHashCanonical(records) {
  const sorted = [...records].sort((a, b) => a.pack_id.localeCompare(b.pack_id));
  return hashInputs(sorted.map((record) => canonJson(record)));
}

function digestMatchesLive(cached, trace, kernelSource) {
  if (!cached?.data?.digest) {
    return false;
  }
  const tail = traceTail(trace);
  const payload = canonJson(tail) + kernelSource;
  const recomputed = sha256Hex(payload);
  if (cached.data.digest !== recomputed) {
    return false;
  }
  if (!cached.data.trace_hash) {
    return true;
  }
  return cached.data.trace_hash === computeTraceHashCanonical(trace.records);
}

function runPhaseACached(pack, grid, ghost, capBytes) {
  const packKey = computePackKey(pack, grid, ghost);
  const phaseAKey = computePhaseAKey(packKey);

  const cached = readCache(phaseAKey);
  if (cached && !invalidateStale(phaseAKey, hashInputs([JSON.stringify(cached.data)]))) {
    return cached.data;
  }

  const result = runPhaseA(pack, grid, ghost, capBytes);
  writeCache(phaseAKey, result, [packKey]);
  return result;
}

function runStageTwoCached(pack, grid, ghost, edgeInfo, packKey) {
  const stageTwoKey = computeStageTwoKey(packKey, edgeInfo);
  const cached = readCache(stageTwoKey);
  if (cached && !invalidateStale(stageTwoKey, hashInputs([JSON.stringify(cached.data)]))) {
    return cached.data;
  }
  const result = runStageTwo(pack, grid, ghost, edgeInfo);
  const edgeDepKey = `edge:${packKey}:${hashInputs([edgeInfo.edge_mode, edgeInfo.peel_rows])}`;
  writeCache(stageTwoKey, result, [packKey, edgeDepKey]);
  return result;
}

function computeDigest(trace, kernelSource, traceKey) {
  const tail = traceTail(trace);
  const payload = canonJson(tail) + kernelSource;
  const digest = sha256Hex(payload);
  const kernelHash = hashInputs([kernelSource]);
  const digestKey = computeDigestKey(traceKey, kernelHash);
  const traceHash = computeTraceHashCanonical(trace.records);
  const cached = readCache(digestKey);
  if (cached && digestMatchesLive(cached, trace, kernelSource)) {
    return cached.data.digest;
  }
  writeCache(digestKey, { digest, trace_hash: traceHash }, [traceKey]);
  return digest;
}

export async function runCompile(specPath, outDir) {
  fs.mkdirSync(outDir, { recursive: true });
  ensureCache();

  let compileEpoch = readEpoch();
  let migrationCompile = false;
  if (isCacheResetPending()) {
    compileEpoch = onCacheReset();
    clearCache();
    migrationCompile = true;
  } else if (compileEpoch === 0) {
    compileEpoch = ensureEpoch();
  }

  const spec = readJsonAt(path.resolve(specPath));
  const ghost = spec.ghost_width;
  const records = [];

  for (const rawPack of spec.packs) {
    const pack = loadPack(rawPack);
    const grid = loadGrid(readJsonAt(path.join(FORGE_ROOT, 'fixtures/grids', pack.grid_fixture)));

    const { tileInfo, edgeInfo } = runPhaseACached(pack, grid, ghost, pack.scratch_cap_bytes);
    const packKey = computePackKey(pack, grid, ghost);
    const { laneInfo, tallied, divisors } = runStageTwoCached(pack, grid, ghost, edgeInfo, packKey);

    const record = packRecordFromStages(pack, tileInfo, edgeInfo, laneInfo, tallied, divisors);
    if (!spillWithinBudget(record, pack.spill_budget)) {
      throw new Error(`spill budget exceeded for pack ${pack.id}`);
    }
    records.push(record);
  }

  const trace = { records };
  const traceKey = `trace:${computeTraceHash(records)}`;
  writeCache(traceKey, { records }, records.map((row) => `pack:${row.pack_id}`));

  const kernelSource = writeKernel(outDir, kernelTemplate());
  fs.writeFileSync(path.join(outDir, 'kernel.mjs'), kernelSource, 'utf8');
  fs.writeFileSync(path.join(outDir, 'pass.trace.json'), JSON.stringify(trace, null, 2) + '\n', 'utf8');

  const digest = computeDigest(trace, kernelSource, traceKey);
  recordEntry(records.length, digest);
  const bindResult = { digest_chain: digest };
  const metrics = buildMetrics(trace, kernelSource, bindResult, null, compileEpoch);

  fs.writeFileSync(path.join(outDir, 'metrics.json'), JSON.stringify(metrics, null, 2) + '\n', 'utf8');
  if (migrationCompile) {
    finalizeMigrationEpoch();
  }
  clearResetFlag();
  return { trace, metrics };
}
EOF

cat > "$FK/pipeline/stage_two.mjs" <<'EOF'
import { lane_pick } from '../passes/vec_schedule.mjs';
import { tally_regs } from '../emit/ledger_acct.mjs';
import { extents } from '../ir/lattice.mjs';
import { readCache, writeCache, hashInputs } from '../lib/persist.mjs';

export function divisorsOf(n) {
  const out = [];
  for (let d = 1; d <= n; d += 1) {
    if (n % d === 0) out.push(d);
  }
  return out;
}

export function sharedDivisors(grid, ghost) {
  const ext = extents(grid, ghost);
  const lists = ext.map((e) => divisorsOf(e));
  return lists[0].filter((d) => lists.every((lst) => lst.includes(d)));
}

export function simulateSpill(pack, laneWidth) {
  const cells = pack.tile[0] * pack.tile[1] * pack.tile[2];
  return Math.floor(cells / laneWidth);
}

export function peelAdjustedSpill(baseSpill, edgeInfo) {
  if (!edgeInfo?.peel_rows) {
    return baseSpill;
  }
  if (edgeInfo.edge_mode === 'duplicate') {
    return baseSpill + edgeInfo.peel_rows * 3;
  }
  return baseSpill + edgeInfo.peel_rows;
}

function computeStageTwoCacheKey(pack, grid, ghost, edgeInfo) {
  const inputs = [
    pack.id,
    pack.spill_budget,
    JSON.stringify(pack.tile),
    grid.nx, grid.ny, grid.nz,
    ghost,
    edgeInfo.edge_mode,
    edgeInfo.peel_rows,
  ];
  return hashInputs(inputs);
}

export function runStageTwo(pack, grid, ghost, edgeInfo) {
  const cacheKey = `stage_two_raw:${pack.id}:${computeStageTwoCacheKey(pack, grid, ghost, edgeInfo)}`;
  const cachedRaw = readCache(cacheKey);
  const divisors = sharedDivisors(grid, ghost);
  const acctState = {
    divisors,
    spill_budget: pack.spill_budget,
    pack,
    grid,
    edgeInfo,
    ghost,
  };
  const laneInfo = lane_pick(pack, acctState);
  let base_spill;
  if (cachedRaw?.data?.base_spill !== undefined) {
    base_spill = cachedRaw.data.base_spill;
  } else {
    base_spill = simulateSpill(pack, laneInfo.lane_width);
    writeCache(cacheKey, { base_spill, lane_width: laneInfo.lane_width, divisors, computed: true }, []);
  }

  const draft = [{
    pack_id: pack.id,
    base_spill,
    edge_mode: edgeInfo.edge_mode,
    peel_rows: edgeInfo.peel_rows,
    lane_width: laneInfo.lane_width,
    divisors: laneInfo.divisors,
  }];
  const tallied = tally_regs(draft, {});
  return { laneInfo, tallied, divisors };
}
EOF

cat > "$FK/pipeline/stage_three.mjs" <<'EOF'
import { bind_seal } from '../emit/metrics_bind.mjs';
import { canonJson } from '../lib/canon_json.mjs';
import { readGeneration, countEntriesForGeneration } from '../lib/replay_log.mjs';

export function traceTail(trace) {
  const last = trace.records[trace.records.length - 1];
  return {
    pack_id: last.pack_id,
    spill_total: last.spill_total,
    scratch_peak: last.scratch_peak,
    edge_mode: last.edge_mode,
    lane_width: last.lane_width,
    divisors: last.divisors,
  };
}

export function runStageThree(trace, kernelSource) {
  return bind_seal(trace, kernelSource);
}

export function aggregateFromLiveTrace(trace) {
  const sourceRecords = trace.records;
  return {
    spill_total: sourceRecords.reduce((acc, row) => acc + (row.spill_total || 0), 0),
    max_scratch_bytes: Math.max(...sourceRecords.map((row) => row.scratch_peak || 0)),
    lane_width_summary: sourceRecords.map((row) => row.lane_width),
  };
}

export function buildMetrics(trace, kernelSource, bindResult, traceKey, compileEpoch) {
  const rolled = aggregateFromLiveTrace(trace);
  const epoch = compileEpoch ?? 1;
  const replayGen = readGeneration();
  return {
    spill_total: rolled.spill_total,
    max_scratch_bytes: rolled.max_scratch_bytes,
    lane_width_summary: rolled.lane_width_summary,
    compile_epoch: epoch,
    replay_generation: replayGen,
    replay_entry_count: countEntriesForGeneration(replayGen),
    digest_chain: bindResult.digest_chain,
    trace_tail_canonical: canonJson(traceTail(trace)),
  };
}

export function validateTraceIntegrity(trace, expectedPackIds) {
  const actualIds = trace.records.map((row) => row.pack_id);
  if (actualIds.length !== expectedPackIds.length) {
    return { valid: false, reason: 'record count mismatch' };
  }
  for (let i = 0; i < expectedPackIds.length; i += 1) {
    if (actualIds[i] !== expectedPackIds[i]) {
      return { valid: false, reason: `pack mismatch at index ${i}` };
    }
  }
  return { valid: true };
}
EOF

rm -rf /app/output
node "$FK/cli/driver.mjs" compile --spec "$FK/specs/operator.json" --out /app/output
