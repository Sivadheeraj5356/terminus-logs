#!/bin/bash
set -euo pipefail

cat > /app/environment/k4/x2/x2_mux.ts <<'EOF'
import * as fs from "fs";
import * as path from "path";

type Pair = { a: string; b: string; rot: number; active: string };

function rootDir(): string {
  return process.env.K4_ROOT || "/app/environment";
}

function parseHold(text: string): { train: Pair; pairs: Pair[] } {
  const train: Pair = { a: "", b: "", rot: 0, active: "" };
  const pairs: Pair[] = [];
  let section = "";
  let cur: Pair | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const sec = line.match(/^\[([^\]]+)\]$/);
    if (sec) {
      section = sec[1];
      if (section.startsWith("pairs.")) {
        cur = { a: "", b: "", rot: 0, active: "" };
        pairs.push(cur);
      } else {
        cur = null;
      }
      continue;
    }
    const kv = line.match(/^([a-z_]+)\s*=\s*"?([^"]+)"?$/);
    if (!kv) continue;
    const k = kv[1];
    let v: string | number = kv[2];
    if (/^\d+$/.test(String(v))) v = parseInt(String(v), 10);
    if (section === "train") {
      if (k === "pair") {
        const parts = String(v).split("|");
        train.a = parts[0] || "";
        train.b = parts[1] || "";
      } else if (k === "rot") train.rot = v as number;
      else if (k === "active") train.active = String(v);
    } else if (cur) {
      if (k === "a") cur.a = String(v);
      else if (k === "b") cur.b = String(v);
      else if (k === "rot") cur.rot = v as number;
      else if (k === "active") cur.active = String(v);
    }
  }
  return { train, pairs };
}

function parseLedger(text: string): { board: string; cids: string[] }[] {
  const shards: { board: string; cids: string[] }[] = [];
  let cur: { board: string; cids: string[] } | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    if (line === "[[shard]]") {
      cur = { board: "", cids: [] };
      shards.push(cur);
      continue;
    }
    if (!cur) continue;
    const m = line.match(/^(\w+)\s*=\s*(.+)$/);
    if (!m) continue;
    if (m[1] === "board") cur.board = m[2].replace(/^"|"$/g, "");
    if (m[1] === "cids") cur.cids = JSON.parse(m[2]);
  }
  return shards;
}

function pairForKey(key: number): Pair {
  const hold = parseHold(
    fs.readFileSync(path.join(rootDir(), "data", "hold_tbl.toml"), "utf8")
  );
  if (hold.train.rot === key) return hold.train;
  for (const p of hold.pairs) {
    if (p.rot === key) return p;
  }
  return hold.train;
}

export function weave_q(stamp: number, prev: string[], key: number): string[] {
  void stamp;
  const pair = pairForKey(key);
  const sides = new Set([pair.a, pair.b].filter(Boolean));
  const shards = parseLedger(
    fs.readFileSync(
      path.join(rootDir(), "data", "long_ctx", "ledger_mfest.toml"),
      "utf8"
    )
  );
  const extra: string[] = [];
  for (const sh of shards) {
    if (sides.has(sh.board)) {
      for (const c of sh.cids) extra.push(c);
    }
  }
  return Array.from(new Set(prev.concat(extra))).sort();
}
EOF

cat > /app/environment/k4/x3/frag_buf.ts <<'EOF'
import * as fs from "fs";
import * as path from "path";

function rootDir(): string {
  return process.env.K4_ROOT || "/app/environment";
}

function loadBinds(): { stamp: number; fam: number; vec: number[] }[] {
  const calDir = path.join(rootDir(), "data", "cal");
  const out: { stamp: number; fam: number; vec: number[] }[] = [];
  for (const name of fs.readdirSync(calDir).sort()) {
    if (!name.endsWith(".json")) continue;
    const j = JSON.parse(fs.readFileSync(path.join(calDir, name), "utf8"));
    out.push({ stamp: j.stamp, fam: j.fam, vec: j.vec.slice() });
  }
  return out;
}

export function span_q(totals: number[], stamp: number, fam: number): number[] {
  void totals;
  void fam;
  const binds = loadBinds();
  const eligible = binds
    .filter((b) => b.stamp <= stamp)
    .sort((a, b) => b.stamp - a.stamp);
  if (eligible.length) return eligible[0].vec.slice();
  const least = binds.slice().sort((a, b) => a.stamp - b.stamp)[0];
  return least.vec.slice();
}
EOF

cat > /app/environment/n8/q1/ops_mux.ts <<'EOF'
import * as fs from "fs";
import * as path from "path";

function rootDir(): string {
  return process.env.K4_ROOT || "/app/environment";
}

function activeForPair(pairId: string): string {
  const text = fs.readFileSync(
    path.join(rootDir(), "data", "hold_tbl.toml"),
    "utf8"
  );
  let section = "";
  let curA = "";
  let curB = "";
  let curActive = "";
  let trainPair = "";
  let trainActive = "";
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const sec = line.match(/^\[([^\]]+)\]$/);
    if (sec) {
      if (section.startsWith("pairs.") && curA && curB) {
        if (`${curA}|${curB}` === pairId) return curActive;
      }
      section = sec[1];
      curA = "";
      curB = "";
      curActive = "";
      continue;
    }
    const kv = line.match(/^([a-z_]+)\s*=\s*"?([^"]+)"?$/);
    if (!kv) continue;
    const k = kv[1];
    const v = kv[2];
    if (section === "train") {
      if (k === "pair") trainPair = v;
      if (k === "active") trainActive = v;
    } else if (section.startsWith("pairs.")) {
      if (k === "a") curA = v;
      if (k === "b") curB = v;
      if (k === "active") curActive = v;
    }
  }
  if (section.startsWith("pairs.") && curA && curB && `${curA}|${curB}` === pairId) {
    return curActive;
  }
  if (trainPair === pairId) return trainActive;
  const left = pairId.split("|")[1] || "";
  return left;
}

export function latch_d(pairId: string, clauses: string[]): string[] {
  const active = activeForPair(pairId).toUpperCase();
  const out: string[] = [];
  for (const c of clauses) {
    const board = (c.split(".")[0] || "").toUpperCase();
    if (board === active) out.push(c);
  }
  return Array.from(new Set(out)).sort();
}
EOF

cat > /app/environment/n8/q4/pack_emit.ts <<'EOF'
import * as fs from "fs";
import * as path from "path";

function rootDir(): string {
  return process.env.K4_ROOT || "/app/environment";
}

function winningStamp(): number {
  const calDir = path.join(rootDir(), "data", "cal");
  let best = 0;
  for (const name of fs.readdirSync(calDir).sort()) {
    if (!name.endsWith(".json")) continue;
    const j = JSON.parse(fs.readFileSync(path.join(calDir, name), "utf8"));
    if (j.stamp > best) best = j.stamp;
  }
  return best;
}

export function emit_v(
  rows: object[],
  fam: number,
  digest: string
): object[] {
  const stamp = winningStamp();
  const out: object[] = [];
  for (let i = 0; i < rows.length; i++) {
    out.push({
      trig_id: `t${i}`,
      metric_fam: fam,
      bind_stamp: stamp,
      hx_ref: digest,
    });
  }
  return out;
}
EOF

chmod +x /app/environment/scripts/build_k4.sh /app/environment/scripts/run_k4.sh /app/environment/tools/obs_k4
bash /app/environment/scripts/build_k4.sh
bash /app/environment/scripts/run_k4.sh \
  --root /app/environment/data/pack_tr \
  --out /app/output/readiness_gonogo_brief.json
