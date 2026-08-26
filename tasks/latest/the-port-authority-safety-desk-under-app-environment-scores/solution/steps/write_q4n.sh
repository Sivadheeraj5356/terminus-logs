#!/bin/bash
set -euo pipefail

cd /app/environment

cat > q4n/phase_a.ts <<'EOF'
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

function sumHits(rows: RotRow[]): number {
  return rows.reduce((acc, row) => acc + row.hits, 0);
}

function sumTotal(rows: RotRow[]): number {
  return rows.reduce((acc, row) => acc + row.total, 0);
}

function countBelowFloor(rows: RotRow[], floor: number): number {
  let tally = 0;
  for (const row of rows) {
    if (row.total < floor) tally += 1;
  }
  return tally;
}

function eligibleRows(rows: RotRow[], floor: number): RotRow[] {
  const out: RotRow[] = [];
  for (const row of rows) {
    if (row.total >= floor) out.push(row);
  }
  return out;
}

export function op_a(rows: RotRow[], floor: number): CoverageSlice {
  const eligible = eligibleRows(rows, floor);
  const hits = sumHits(eligible);
  const total = sumTotal(eligible);
  const ratio = total > 0 ? hits / total : 0;
  const under_tally = countBelowFloor(rows, floor);
  return { eligible, ratio, under_tally };
}
EOF
