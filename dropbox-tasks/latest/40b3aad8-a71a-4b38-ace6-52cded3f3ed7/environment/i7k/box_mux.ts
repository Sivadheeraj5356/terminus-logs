import * as fs from "fs";
import * as yaml from "js-yaml";
import type { BoxCtx, RowRec, YamlSink } from "../lib/types";

const COMPILE_LANE = 6;

function readLaneLimit(cfgPath: string): number {
  const raw = fs.readFileSync(cfgPath, "utf8");
  const doc = yaml.load(raw) as Record<string, unknown>;
  const publish = doc.lane_limit_publish;
  if (typeof publish === "number") {
    return publish;
  }
  return COMPILE_LANE;
}

export function enclose_ivk(
  ctx: BoxCtx,
  recs: RowRec[],
  n: number,
  sink: YamlSink
): number {
  if (!ctx || !recs || !sink || n < 0) {
    return -1;
  }
  const cap = COMPILE_LANE;
  const limit = Math.min(n, cap);
  for (let i = 0; i < limit; i += 1) {
    sink.push(recs[i]);
  }
  return limit;
}

export { readLaneLimit };
