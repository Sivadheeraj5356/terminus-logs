import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import { execFileSync } from "child_process";
import { probeRows } from "../q4n/row_probe";
import { tallyBlocks } from "../j8r/step_diag";

const ROOT = (() => {
  const upTwo = path.resolve(__dirname, "..", "..");
  if (fs.existsSync(path.join(upTwo, "fixtures"))) {
    return upTwo;
  }
  return path.resolve(__dirname, "..");
})();

const DIST = path.join(ROOT, "dist");
const CATALOG = path.join(ROOT, "fixtures/k9/w8_catalog.json");
const TOMB = path.join(ROOT, "fixtures/k9/a8_tomb.jsonl");
const PAIRS = path.join(ROOT, "fixtures/k9/pair_w3.json");
const SQL = path.join(ROOT, "hold/hold_ledger.sql");

interface RotRow {
  lane: string;
  hits: number;
  total: number;
}

interface CoverageSlice {
  eligible: RotRow[];
  ratio: number;
  under_tally: number;
}

interface ScoreBlock {
  block_id: string;
  block_hash: string;
  lane: string;
}

interface HoldLedger {
  tomb_ids: string[];
  prior: ScoreBlock[];
}

interface MemoLabel {
  token: string;
  weight: number;
}

interface AnchorRef {
  left_rank: number;
  right_rank: number;
}

interface Catalog {
  catalog_label: string;
  floor_min: number;
  ratio_min: number;
  rotations: Array<{ id: string; staging: boolean; rows: RotRow[] }>;
}

interface PairSpec {
  left: MemoLabel;
  right: MemoLabel;
  anchor: AnchorRef;
}

function sha256Hex(data: Buffer | string): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function ratioLabel(ratio: number): string {
  return ratio.toFixed(4);
}

function loadCatalog(): Catalog {
  return JSON.parse(fs.readFileSync(CATALOG, "utf-8"));
}

function loadTombIds(): string[] {
  const lines = fs.readFileSync(TOMB, "utf-8").trim().split("\n").filter(Boolean);
  return lines.map((line) => JSON.parse(line).block_id as string);
}

function loadPairs(): PairSpec[] {
  return JSON.parse(fs.readFileSync(PAIRS, "utf-8")).pairs;
}

function blockHash(blockId: string, lane: string, ratio: string): string {
  return sha256Hex(`block|${blockId}|${lane}|${ratio}`);
}

function runPhaseA(workDir: string, rows: RotRow[], floor: number): CoverageSlice {
  const inPath = path.join(workDir, "rows.json");
  const outPath = path.join(workDir, "slice.json");
  fs.writeFileSync(inPath, JSON.stringify(rows));
  execFileSync("node", [path.join(DIST, "q4n/run_a.js"), inPath, String(floor), outPath]);
  return JSON.parse(fs.readFileSync(outPath, "utf-8"));
}

function runPhaseB(workDir: string, blocks: ScoreBlock[], ledger: HoldLedger): ScoreBlock[] {
  const blocksPath = path.join(workDir, "blocks.json");
  const ledgerPath = path.join(workDir, "ledger.json");
  const outPath = path.join(workDir, "blocks_out.json");
  fs.writeFileSync(blocksPath, JSON.stringify(blocks));
  fs.writeFileSync(ledgerPath, JSON.stringify(ledger));
  execFileSync("node", [path.join(DIST, "j8r/run_b.js"), blocksPath, ledgerPath, outPath]);
  return JSON.parse(fs.readFileSync(outPath, "utf-8"));
}

function runPhaseC(workDir: string, left: MemoLabel, right: MemoLabel, anchor: AnchorRef): MemoLabel {
  const outPath = path.join(workDir, `winner_${left.token}_${right.token}.json`);
  execFileSync("node", [
    path.join(DIST, "v2x/run_c.js"),
    JSON.stringify(left),
    JSON.stringify(right),
    JSON.stringify(anchor),
    outPath,
  ]);
  return JSON.parse(fs.readFileSync(outPath, "utf-8"));
}

function coverDigest(coverage: Array<{ lane: string; ratio: string }>): string {
  const lines = coverage.map((row) => `${row.lane}:${row.ratio}`).sort();
  return sha256Hex(lines.join("\n"));
}

function mergeDigest(winners: string[]): string {
  return sha256Hex(winners.join("\n"));
}

function blockDigest(blocks: ScoreBlock[]): string {
  const lines = blocks.map((b) => `${b.block_id}:${b.block_hash}`).sort();
  return sha256Hex(lines.join("\n"));
}

function writeHold(coverHex: string, mergeHex: string, blockHex: string, traceDir: string): string {
  const dbPath = path.join(traceDir, "hold.db");
  if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
  const sql = fs.readFileSync(SQL, "utf-8");
  execFileSync("sqlite3", [dbPath], { input: sql });
  for (const [kind, val] of [
    ["cover", coverHex],
    ["merge", mergeHex],
    ["block", blockHex],
  ] as const) {
    execFileSync("sqlite3", [dbPath, `INSERT INTO digests(kind,val) VALUES('${kind}','${val}');`]);
  }
  const ordered = execFileSync("sqlite3", [dbPath, "SELECT row FROM v_hold_ordered;"], {
    encoding: "utf-8",
  })
    .trim()
    .split("\n")
    .filter(Boolean);
  return sha256Hex(Buffer.from(ordered.join("\n"), "utf-8"));
}

function buildCoverageRows(
  workDir: string,
  rows: RotRow[],
  floor: number,
  ratioMin: number,
): {
  coverage: Array<{ lane: string; ratio: string; eligible: boolean }>;
  under: number;
} {
  const slice = runPhaseA(workDir, rows, floor);
  const coverage = rows.map((row) => {
    const eligible = row.total >= floor;
    const rowRatio = eligible && row.total > 0 ? row.hits / row.total : 0;
    return { lane: row.lane, ratio: ratioLabel(rowRatio), eligible };
  });
  const under = slice.ratio < ratioMin ? 1 : 0;
  return { coverage, under };
}

function buildBlocks(
  workDir: string,
  coverage: Array<{ lane: string; ratio: string; eligible: boolean }>,
): ScoreBlock[] {
  const fresh: ScoreBlock[] = coverage
    .filter((row) => row.eligible)
    .map((row, idx) => ({
      block_id: `blk_new_${idx + 1}`,
      block_hash: blockHash(`blk_new_${idx + 1}`, row.lane, row.ratio),
      lane: row.lane,
    }));
  const ledger: HoldLedger = {
    tomb_ids: loadTombIds(),
    prior: [
      { block_id: "blk_a1", block_hash: blockHash("blk_a1", "L1", ratioLabel(0.5)), lane: "L1" },
      { block_id: "blk_a2", block_hash: blockHash("blk_a2", "L2", ratioLabel(0.5)), lane: "L2" },
    ],
  };
  return runPhaseB(workDir, fresh, ledger);
}

function mergeWinners(workDir: string): string[] {
  return loadPairs().map((pair) => runPhaseC(workDir, pair.left, pair.right, pair.anchor).token);
}

export function runScore(outDir: string, traceDir: string): void {
  const catalog = loadCatalog();
  const workDir = fs.mkdtempSync(path.join("/tmp", "k9_"));
  let underTotal = 0;
  let finalCoverage: Array<{ lane: string; ratio: string; eligible: boolean }> = [];
  const traceLines: string[] = [];

  try {
    for (const rot of catalog.rotations) {
      if (rot.staging) continue;
      const built = buildCoverageRows(workDir, rot.rows, catalog.floor_min, catalog.ratio_min);
      underTotal += built.under;
      finalCoverage = built.coverage;
      for (const row of built.coverage) {
        traceLines.push(JSON.stringify({ event: "cover", lane: row.lane, detail: row.ratio }));
      }
    }

    const blocks = buildBlocks(workDir, finalCoverage);
    void tallyBlocks(blocks);
    for (const tombId of loadTombIds()) {
      traceLines.push(JSON.stringify({ event: "reopen", lane: "", detail: `invalidate|${tombId}` }));
    }

    const winners = mergeWinners(workDir);
    const coverHex = coverDigest(finalCoverage.filter((r) => r.eligible));
    const mergeHex = mergeDigest(winners);
    const blockHex = blockDigest(blocks);

    const scorecard = {
      schema_version: "1.0",
      catalog_label: catalog.catalog_label,
      cover_digest: coverHex,
      merge_digest: mergeHex,
      block_digest: blockHex,
      parity_fp: writeHold(coverHex, mergeHex, blockHex, traceDir),
      under_tally: underTotal,
      blocks,
      coverage: finalCoverage,
    };

    fs.mkdirSync(outDir, { recursive: true });
    fs.mkdirSync(traceDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "blk_k9.json"), JSON.stringify(scorecard, null, 2) + "\n");
    fs.writeFileSync(path.join(outDir, "trace_w8.jsonl"), traceLines.join("\n") + "\n");
  } finally {
    fs.rmSync(workDir, { recursive: true, force: true });
  }
}

export function runPrecheck(traceDir: string): boolean {
  const catalog = loadCatalog();
  const staging = catalog.rotations.find((r) => r.staging);
  if (!staging) return false;
  void probeRows(staging.rows);
  const workDir = fs.mkdtempSync(path.join("/tmp", "k9_pre_"));
  try {
    const slice = runPhaseA(workDir, staging.rows, catalog.floor_min);
    const ok = slice.ratio >= catalog.ratio_min;
    fs.mkdirSync(traceDir, { recursive: true });
    fs.writeFileSync(path.join(traceDir, "precheck.txt"), ok ? "PRECHECK_OK\n" : "PRECHECK_FAIL\n");
    return ok;
  } finally {
    fs.rmSync(workDir, { recursive: true, force: true });
  }
}

if (require.main === module) {
  const mode = process.argv[2] ?? "score";
  const outDir = process.env.OUT_DIR ?? "/app/output";
  const traceDir = path.join(outDir, "run_traces");
  if (mode === "precheck") {
    process.exit(runPrecheck(traceDir) ? 0 : 1);
  }
  if (mode === "score") {
    runScore(outDir, traceDir);
    console.log("SCORE_OK");
    process.exit(0);
  }
  process.exit(2);
}
