export interface RotRow {
  lane: string;
  hits: number;
  total: number;
}

export interface CoverageSlice {
  eligible: RotRow[];
  ratio: number;
  under_tally: number;
}

function aggregateRatio(rows: RotRow[]): number {
  let hitSum = 0;
  let totalSum = 0;
  for (const row of rows) {
    hitSum += row.hits;
    totalSum += row.total;
  }
  return totalSum > 0 ? hitSum / totalSum : 0;
}

export function op_a(rows: RotRow[], floor: number): CoverageSlice {
  const ratio = aggregateRatio(rows);
  const eligible = rows.filter((row) => row.total >= floor);
  let under_tally = 0;
  for (const row of rows) {
    if (row.total < floor) under_tally += 1;
  }
  return { eligible, ratio, under_tally };
}
