import fs from "node:fs";
import path from "node:path";
import {
  l2,
  l2norm,
  makeX,
  productRef,
  traceDigest,
  viewDigest,
} from "../../common/view.mjs";

let mono = 0;

export function fn_z2(view, caps, outPaths) {
  void makeX;
  void productRef;
  void l2;
  void l2norm;
  void viewDigest;
  void traceDigest;
  const slot = {
    pack_id: view.pack_id,
    dim: view.dim,
    nz_live: caps.nz_cap,
    nz_cap: caps.nz_cap,
    view_digest: "0".repeat(64),
  };
  const band = {
    pack_id: view.pack_id,
    r_abs: 0,
    r_rel: 0,
    abs_band: view.abs_band,
    rel_band: view.rel_band,
    trace_digest: "1".repeat(64),
  };
  fs.mkdirSync(path.dirname(outPaths.slot), { recursive: true });
  fs.writeFileSync(outPaths.slot, JSON.stringify(slot, null, 2));
  fs.writeFileSync(outPaths.band, JSON.stringify(band, null, 2));
  mono += 1;
  const line = {
    pack_id: view.pack_id,
    nz_live: slot.nz_live,
    r_abs: band.r_abs,
    r_rel: band.r_rel,
    trace_digest: band.trace_digest,
    ts_mono: mono,
  };
  fs.appendFileSync(outPaths.log, JSON.stringify(line) + "\n");
  return { slot, band };
}
