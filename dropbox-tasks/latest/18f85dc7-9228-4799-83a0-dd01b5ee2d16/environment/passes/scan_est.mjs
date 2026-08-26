export function estimateRegs(traceSlice) {
  let total = 0;
  for (const row of traceSlice) {
    total += row.spill_total ?? 0;
  }
  return total;
}
