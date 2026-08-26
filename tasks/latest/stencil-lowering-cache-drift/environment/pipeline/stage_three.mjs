import { bind_seal } from '../emit/metrics_bind.mjs';
import { canonJson } from '../lib/canon_json.mjs';
import { readCache } from '../lib/persist.mjs';
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

function rollupRows(trace, traceKey) {
  if (!traceKey) {
    return trace.records;
  }
  const cached = readCache(traceKey);
  if (!cached?.data?.records) {
    return trace.records;
  }
  return [...cached.data.records].sort((a, b) => b.lane_width - a.lane_width);
}

export function buildMetrics(trace, kernelSource, bindResult, traceKey, compileEpoch) {
  const rows = rollupRows(trace, traceKey);
  const spill_total = rows.reduce((acc, row) => acc + (row.spill_total || 0), 0);
  const max_scratch = Math.max(...trace.records.map((row) => row.scratch_peak || 0));
  const lane_width_summary = rows.map((row) => row.lane_width);
  const epoch = compileEpoch ?? 1;
  const replayGen = readGeneration();

  return {
    spill_total,
    max_scratch_bytes: max_scratch,
    lane_width_summary,
    compile_epoch: epoch,
    replay_generation: replayGen > 0 ? replayGen - 1 : 0,
    replay_entry_count: rows.length,
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
