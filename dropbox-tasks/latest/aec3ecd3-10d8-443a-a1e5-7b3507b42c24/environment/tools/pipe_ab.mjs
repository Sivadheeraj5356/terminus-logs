import { fn_p3 } from "../p3k/src/lane_a.mjs";
import { fn_w8 } from "../w8n/src/lane_b.mjs";
import { cloneView, defaultPerm } from "../common/view.mjs";

export function stage_ab(raw) {
  const perm = defaultPerm(raw.dim);
  const after = fn_p3(cloneView(raw), perm);
  const live = fn_w8(after, after.dim);
  return { after, live, perm };
}
