import type { RotRow } from "./phase_a";

/** Tallies raw row counts without export semantics. */
export function probeRows(rows: RotRow[]): number {
  return rows.reduce((acc, row) => acc + row.total, 0);
}
