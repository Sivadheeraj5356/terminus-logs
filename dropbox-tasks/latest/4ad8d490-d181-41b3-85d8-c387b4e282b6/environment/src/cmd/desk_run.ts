import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import { stage_join } from "../stages/stage_a";
import { stage_span } from "../stages/stage_b";
import { stage_latch } from "../stages/stage_c";
import { stage_emit } from "../stages/stage_d";
import { mux_note } from "../../k4/x2/mux_note";
import { frag_scan } from "../../k4/x3/frag_scan";
import { ops_buf } from "../../n8/q1/ops_buf";
import { pack_note } from "../../n8/q4/pack_note";

type GateRow = {
  row_id: string;
  board_pair: string;
  clause_ids: string[];
  seg_vec: number[];
  disc_bind: string[];
  gate_kind: string;
};

function argVal(flag: string, argv: string[], fallback: string): string {
  const i = argv.indexOf(flag);
  if (i >= 0 && i + 1 < argv.length) return argv[i + 1];
  return fallback;
}

function envRoot(argv: string[]): string {
  return argVal("--env", argv, process.env.K4_ROOT || "/app/environment");
}

function readJson(p: string): any {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function loadBinds(calDir: string): { stamp: number; fam: number; vec: number[] }[] {
  const out: { stamp: number; fam: number; vec: number[] }[] = [];
  for (const name of fs.readdirSync(calDir).sort()) {
    if (!name.endsWith(".json")) continue;
    const j = readJson(path.join(calDir, name));
    out.push({ stamp: j.stamp, fam: j.fam, vec: j.vec.slice() });
  }
  return out;
}

function pickBind(
  binds: { stamp: number; fam: number; vec: number[] }[],
  S: number
): { stamp: number; fam: number; vec: number[] } {
  const eligible = binds
    .filter((b) => b.stamp <= S)
    .sort((a, b) => b.stamp - a.stamp);
  if (eligible.length) return eligible[0];
  return binds.slice().sort((a, b) => a.stamp - b.stamp)[0];
}

function sum(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0);
}

function hxOf(gate_rows: GateRow[], seg_trace: object): string {
  const payload = JSON.stringify({ gate_rows, seg_trace });
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex");
}

function loadRootPack(root: string): {
  pair: string;
  rot: number;
  active: string;
  seeds: string[];
} {
  const manPath = path.join(root, "wk", "manifest.json");
  if (!fs.existsSync(manPath)) {
    throw new Error(`no pack root at ${root}`);
  }
  const man = readJson(manPath);
  const seeds: string[] = [];
  for (const n of man.nets as string[]) {
    const net = readJson(path.join(root, "wk", n));
    for (const c of net.seed_cids as string[]) seeds.push(c);
  }
  return {
    pair: man.pair,
    rot: man.rot,
    active: man.active,
    seeds: Array.from(new Set(seeds)).sort(),
  };
}

function main(): void {
  const argv = process.argv.slice(2);
  const env = envRoot(argv);
  process.env.K4_ROOT = env;
  const root = argVal("--root", argv, path.join(env, "data", "pack_tr"));
  const outPath = argVal(
    "--out",
    argv,
    "/app/output/readiness_gonogo_brief.json"
  );

  void mux_note(["a", "b"]);
  void frag_scan(fs.readdirSync(path.join(env, "data", "cal")));
  void ops_buf(["x"]);
  void pack_note([{}]);

  const pack = loadRootPack(root);
  const binds = loadBinds(path.join(env, "data", "cal"));
  const maxStamp = Math.max(...binds.map((b) => b.stamp));
  const win = pickBind(binds, maxStamp);

  const joined = stage_join(maxStamp, pack.seeds, pack.rot);
  const vec = stage_span(binds[0].vec.slice(), maxStamp, win.fam);
  const disc = stage_latch(pack.pair, joined);

  const gate: GateRow = {
    row_id: "g0",
    board_pair: pack.pair,
    clause_ids: joined.slice().sort(),
    seg_vec: vec.slice(),
    disc_bind: disc.slice().sort(),
    gate_kind: disc.length > 0 && sum(vec) > 0 ? "go" : "nogo",
  };

  const seg_trace = { vec: vec.slice(), stamp: win.stamp, fam: win.fam };
  const seal_hx = hxOf([gate], seg_trace);
  const rb = stage_emit([gate], win.fam, seal_hx) as Array<{
    trig_id: string;
    metric_fam: number;
    bind_stamp: number;
    hx_ref: string;
  }>;
  for (const r of rb) {
    r.hx_ref = seal_hx;
  }

  const finalDoc = {
    schema_ver: 1,
    brief_digest: seal_hx,
    gate_rows: [gate],
    rb_rows: rb,
    seg_trace,
  };

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(finalDoc, null, 2) + "\n", "utf8");
}

main();
