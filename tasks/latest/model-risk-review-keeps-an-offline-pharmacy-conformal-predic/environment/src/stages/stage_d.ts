import { emit_v } from "../../n8/q4/pack_emit";

export function stage_emit(
  rows: object[],
  fam: number,
  digest: string
): object[] {
  return emit_v(rows, fam, digest);
}
