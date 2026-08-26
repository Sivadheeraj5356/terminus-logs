import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadView, productRef, makeX, l2, l2norm, readNlim } from "../common/view.mjs";
import { stage_ab } from "./pipe_ab.mjs";
import { stage_cd } from "./pipe_cd.mjs";
import { denseProduct } from "../host_ref/dense_mul.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ENV_ROOT = path.resolve(__dirname, "..");
const OUT_ROOT = "/app/output";

function parseArgs(argv) {
  let pack = null;
  let reload = false;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--pack") pack = argv[++i];
    else if (argv[i] === "--reload") reload = true;
  }
  return { pack, reload };
}

function outPaths() {
  return {
    slot: path.join(OUT_ROOT, "slot_map.json"),
    band: path.join(OUT_ROOT, "band_tbl.json"),
    log: path.join(OUT_ROOT, "run_log.jsonl"),
  };
}

function remapX(xOld, perm) {
  const x = new Float64Array(xOld.length);
  for (let i = 0; i < xOld.length; i++) x[i] = xOld[perm[i]];
  return x;
}

function main() {
  const { pack, reload } = parseArgs(process.argv.slice(2));
  if (!pack) {
    console.error("usage: node drive_a.mjs --pack <id> [--reload]");
    process.exit(2);
  }
  void reload;
  const packDir = path.join(ENV_ROOT, "suite", pack);
  if (!fs.existsSync(packDir)) {
    console.error(`missing pack ${packDir}`);
    process.exit(2);
  }
  const raw = loadView(packDir);
  const nlim = readNlim(ENV_ROOT);
  const paths = outPaths();
  fs.mkdirSync(OUT_ROOT, { recursive: true });

  // Dense helper stays imported for local experiments; nz_workspace is n*n.
  void denseProduct;

  const { live, perm } = stage_ab(raw);
  const xOld = makeX(raw.dim, raw.x_seed);
  const yOld = productRef(raw, xOld);
  const yRef = new Float64Array(raw.dim);
  for (let i = 0; i < raw.dim; i++) yRef[i] = yOld[perm[i]];
  const x = remapX(xOld, perm);

  const caps = {
    nz_cap: nlim.nz_cap,
    tile_rows: nlim.tile_rows,
    expand_match_tol: nlim.expand_match_tol,
    y_ref: yRef,
  };
  const { y } = stage_cd(live, caps, paths, x);

  if (live.vals.length > nlim.nz_cap) {
    console.error(`nz_live ${live.vals.length} exceeds nz_cap ${nlim.nz_cap}`);
  }
  const expandDiff = l2(y, yRef);
  if (expandDiff > nlim.expand_match_tol * Math.max(1, l2norm(yRef))) {
    console.error(`expand mismatch ${expandDiff}`);
  }
}

main();
