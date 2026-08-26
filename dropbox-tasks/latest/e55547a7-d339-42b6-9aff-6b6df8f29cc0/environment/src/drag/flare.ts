import { FlareEvent } from "../types";

export function currentDensityScale(flares: FlareEvent[], tSec: number): number {
  let scale = 1.0;
  for (const f of flares) {
    if (tSec >= f.t_sec) {
      scale *= f.density_scale;
    }
  }
  return scale;
}
