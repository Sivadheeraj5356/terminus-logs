export function tally_regs(traceSlice, kernelMeta) {
  const rows = traceSlice.map((row) => {
    let spill_total = row.base_spill ?? 0;
    // Add peel spill based on edge mode
    if (row.edge_mode === 'duplicate') {
      spill_total += (row.peel_rows ?? 0) * 3;
    } else {
      spill_total += row.peel_rows ?? 0;
    }
    return { ...row, spill_total };
  });
  const spill_total = rows.reduce((acc, row) => acc + row.spill_total, 0);
  return { rows, spill_total };
}
