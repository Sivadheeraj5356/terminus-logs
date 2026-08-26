import { weave_q } from "../../k4/x2/x2_mux";

export function stage_join(
  stamp: number,
  prev: string[],
  key: number
): string[] {
  return weave_q(stamp, prev, key);
}
