
import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import { stepFold } from "./step_fold";
import { stepMix } from "./step_mix";
import { stepKnit } from "./step_knit";
import { previewSlots } from "../q9/decoy_k4";
import { scoreboardSum } from "../w2/decoy_n8";
import { themeHex } from "../v7/decoy_p3";
import { cellIndex, loadCases, loadMap } from "../src/board_io";
import { CaseRow, MapSpec } from "../src/types";

function wallSet(map: MapSpec): Set<string> {
  const s = new Set<string>();
  for (const w of map.walls) {
    s.add(w[0] + "," + w[1]);
  }
  return s;
}

function lockedCells(map: MapSpec): number[] {
  const cells: number[] = [];
  const ordered = map.players.slice().sort((a, b) => a.id - b.id);
  for (const p of ordered) {
    cells.push(cellIndex(map.width, p.intent[0], p.intent[1]));
  }
  return cells;
}

function litFromLocked(map: MapSpec, cells: number[]): number[] {
  const walls = wallSet(map);
  const lit = new Set<number>();
  for (const cell of cells) {
    const x0 = cell % map.width;
    const y0 = Math.floor(cell / map.width);
    for (let y = 0; y < map.height; y++) {
      for (let x = 0; x < map.width; x++) {
        if (walls.has(x + "," + y)) {
          continue;
        }
        const d = Math.abs(x - x0) + Math.abs(y - y0);
        if (d <= 2) {
          lit.add(cellIndex(map.width, x, y));
        }
      }
    }
  }
  return Array.from(lit).sort((a, b) => a - b);
}

export function runCases(casesPath: string, outDir: string): void {
  const fixturesRoot = path.dirname(casesPath);
  const cases = loadCases(casesPath);
  fs.mkdirSync(outDir, { recursive: true });

  const rows: CaseRow[] = [];
  const vlines: string[] = [];

  for (const c of cases) {
    const map = loadMap(fixturesRoot, c.map);
    const cells = lockedCells(map);
    const slots = Uint32Array.from(cells);
    void previewSlots(slots);
    void scoreboardSum(cells);
    void themeHex(c.epoch);

    const digest = stepFold(slots, c.salt);
    const mix = stepMix(0, cells, c.weight);
    const cert = stepKnit(digest, c.epoch, cells);
    const lit = litFromLocked(map, cells);
    const sortedCells = cells.slice().sort((a, b) => a - b);

    rows.push({
      id: c.id,
      epoch: c.epoch,
      digest,
      mix,
      cert,
      cells: sortedCells,
      lit,
    });
    vlines.push(
      JSON.stringify({
        id: c.id,
        epoch: c.epoch,
        digest,
        cert,
        cells: sortedCells,
      })
    );
  }

  const run_digest = crypto
    .createHash("sha256")
    .update(rows.map((r) => r.digest).join("|"), "utf8")
    .digest("hex")
    .slice(0, 16);

  fs.writeFileSync(
    path.join(outDir, "sheet.json"),
    JSON.stringify({ cases: rows, run_digest }, null, 2) + "\n"
  );
  fs.writeFileSync(path.join(outDir, "vlog.jsonl"), vlines.join("\n") + "\n");
}
