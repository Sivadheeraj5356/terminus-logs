import { fn_w3 } from '../w3q/topo_mux';

export function runTopoStep(seed: number, laneTbl: Record<string, string>, outDir: string): [number, Buffer] {
  return fn_w3(String(seed), { slot: laneTbl.slot || '0' }, outDir);
}
