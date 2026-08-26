import { fn_h2 } from '../h2k/flag_mux';

export function runExpandStep(seed: number, armTbl: Record<string, string>, gate: boolean): [number, Buffer] {
  return fn_h2(String(seed), armTbl, gate ? 0 : 1);
}
