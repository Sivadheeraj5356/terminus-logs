export function lane_pick(pack, acctState) {
  const divisors = [...(acctState.divisors ?? [1])].sort((a, b) => b - a);
  const budget = acctState.spill_budget ?? Number.MAX_SAFE_INTEGER;
  const edgeInfo = acctState.edgeInfo;
  const cells = pack.tile[0] * pack.tile[1] * pack.tile[2];
  
  // Find the largest divisor <= 8 that keeps spill within budget
  let lane_width = 1;
  for (const candidate of divisors) {
    if (candidate > 8) continue;
    
    // Compute spill including edge peel overhead
    let spill = Math.floor(cells / candidate);
    if (edgeInfo && edgeInfo.peel_rows) {
      if (edgeInfo.edge_mode === 'duplicate') {
        spill += edgeInfo.peel_rows * 3;
      } else {
        spill += edgeInfo.peel_rows;
      }
    }
    
    if (spill <= budget) {
      lane_width = candidate;
      break;
    }
  }
  
  return { lane_width, divisors };
}
