import { latch_d } from "../../n8/q1/ops_mux";

export function stage_latch(pairId: string, clauses: string[]): string[] {
  return latch_d(pairId, clauses);
}
