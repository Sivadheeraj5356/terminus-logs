
import * as fs from "fs";
import * as path from "path";
import { CaseSpec, MapSpec } from "./types";

export function loadCases(casesPath: string): CaseSpec[] {
  const raw = fs.readFileSync(casesPath, "utf8");
  const blocks = raw.split("[[case]]").slice(1);
  const out: CaseSpec[] = [];
  for (const block of blocks) {
    const get = (key: string): string => {
      const re = new RegExp("^\\s*" + key + "\\s*=\\s*\"?([^\"\\n]+)\"?", "m");
      const m = block.match(re);
      if (!m) {
        throw new Error("missing " + key);
      }
      return m[1].trim();
    };
    out.push({
      id: get("id"),
      map: get("map"),
      epoch: parseInt(get("epoch"), 10),
      salt: parseInt(get("salt"), 10),
      weight: parseInt(get("weight"), 10),
    });
  }
  return out;
}

export function loadMap(fixturesRoot: string, rel: string): MapSpec {
  const full = path.join(fixturesRoot, rel);
  return JSON.parse(fs.readFileSync(full, "utf8")) as MapSpec;
}

export function cellIndex(width: number, x: number, y: number): number {
  return y * width + x;
}
