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

function computeStageTwoCacheKey(pack, grid, ghost) {
  const inputs = [
    pack.id,
    pack.spill_budget,
    JSON.stringify(pack.tile),
    grid.nx, grid.ny, grid.nz,
    ghost,
  ];
  return hashInputs(inputs);
}

export function runStageTwo(pack, grid, ghost, edgeInfo) {
  const cacheKey = `stage_two_raw:${pack.id}:${computeStageTwoCacheKey(pack, grid, ghost)}`;
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
    writeCache(cacheKey, { base_spill, lane_width: laneInfo.lane_width, divisors }, []);
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
