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
import { ensureCache, readCache, writeCache, hashInputs, invalidateStale } from '../lib/persist.mjs';
import { ensureEpoch, onCacheReset, readEpoch } from '../lib/journal.mjs';
import { recordEntry } from '../lib/replay_log.mjs';
import { tally_regs } from '../emit/ledger_acct.mjs';
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

function computeStageTwoKey(packKey) {
  return `stage_two:${packKey}`;
}

function computeDigestKey(traceKey, kernelHash) {
  return `digest:${traceKey}:${kernelHash}`;
}

function refreshCachedStage(cached, edgeInfo, pack) {
  if (!cached?.laneInfo || !cached?.tallied) {
    return cached;
  }
  const draft = [{
    pack_id: pack.id,
    base_spill: cached.tallied.spill_total,
    edge_mode: edgeInfo.edge_mode,
    peel_rows: edgeInfo.peel_rows,
    lane_width: cached.laneInfo.lane_width,
    divisors: cached.laneInfo.divisors,
  }];
  const tallied = tally_regs(draft, {});
  return { ...cached, tallied };
}

function runPhaseACached(pack, grid, ghost, capBytes) {
  const packKey = computePackKey(pack, grid, ghost);
  const phaseAKey = computePhaseAKey(packKey);

  const cached = readCache(phaseAKey);
  if (cached && !invalidateStale(phaseAKey)) {
    return cached.data;
  }

  const result = runPhaseA(pack, grid, ghost, capBytes);
  writeCache(phaseAKey, result, [packKey]);
  return result;
}

function runStageTwoCached(pack, grid, ghost, edgeInfo, packKey) {
  const stageTwoKey = computeStageTwoKey(packKey);

  const cached = readCache(stageTwoKey);
  if (cached?.data) {
    const refreshed = refreshCachedStage(cached.data, edgeInfo, pack);
    writeCache(stageTwoKey, refreshed, [packKey]);
    return refreshed;
  }

  const result = runStageTwo(pack, grid, ghost, edgeInfo);
  writeCache(stageTwoKey, result, [packKey]);
  return result;
}

function computeTraceHash(records) {
  return hashInputs(records.map((record) => JSON.stringify(record)));
}

function computeTraceHashCanonical(records) {
  const sorted = [...records].sort((a, b) => a.pack_id.localeCompare(b.pack_id));
  return hashInputs(sorted.map((record) => canonJson(record)));
}

function computeDigest(trace, kernelSource, traceKey) {
  const kernelHash = hashInputs([kernelSource]);
  const digestKey = computeDigestKey(traceKey, kernelHash);
  const cached = readCache(digestKey);
  if (cached?.data?.digest) {
    return cached.data.digest;
  }

  const tail = traceTail(trace);
  const payload = canonJson(tail) + kernelSource;
  const digest = sha256Hex(payload);
  const traceHash = computeTraceHashCanonical(trace.records);
  writeCache(digestKey, { digest, trace_hash: traceHash }, [traceKey]);
  return digest;
}

export async function runCompile(specPath, outDir) {
  fs.mkdirSync(outDir, { recursive: true });
  ensureCache();

  let compileEpoch = readEpoch();
  if (isCacheResetPending()) {
    const cacheMod = await import('../lib/persist.mjs');
    cacheMod.clearCache();
    compileEpoch = onCacheReset();
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

    records.push({
      pack_id: pack.id,
      tile: tileInfo.tile,
      scratch_peak: tileInfo.scratch_peak,
      edge_mode: edgeInfo.edge_mode,
      peel_rows: edgeInfo.peel_rows,
      lane_width: laneInfo.lane_width,
      divisors,
      spill_total: tallied.spill_total,
    });
  }

  const trace = { records };
  const traceKey = `trace:${computeTraceHash(records)}`;
  writeCache(traceKey, { records }, records.map((row) => `pack:${row.pack_id}`));

  const kernelSource = writeKernel(outDir, kernelTemplate());
  fs.writeFileSync(path.join(outDir, 'kernel.mjs'), kernelSource, 'utf8');
  fs.writeFileSync(path.join(outDir, 'pass.trace.json'), JSON.stringify(trace, null, 2) + '\n', 'utf8');

  const digest = computeDigest(trace, kernelSource, traceKey);
  const bindResult = { digest_chain: digest };
  const metrics = buildMetrics(trace, kernelSource, bindResult, traceKey, compileEpoch);

  fs.writeFileSync(path.join(outDir, 'metrics.json'), JSON.stringify(metrics, null, 2) + '\n', 'utf8');
  recordEntry(records.length, digest);
  clearResetFlag();
  return { trace, metrics };
}
