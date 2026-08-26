import { span_q } from "../../k4/x3/frag_buf";

export function stage_span(
  totals: number[],
  stamp: number,
  fam: number
): number[] {
  return span_q(totals, stamp, fam);
}
