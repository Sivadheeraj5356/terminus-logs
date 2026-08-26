import { fn_q5 } from "../q5r/src/lane_c.mjs";
import { fn_z2 } from "../z2m/src/lane_d.mjs";

export function stage_cd(live, caps, outPaths, x) {
  const y = fn_q5(live, x, caps.tile_rows);
  const caps2 = { ...caps, probe_y: y };
  const emit = fn_z2(live, caps2, outPaths);
  return { y, emit, x };
}
