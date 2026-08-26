import { execFileSync } from "node:child_process";

const BRIDGE = process.env.G7_BRIDGE ?? "/app/environment/bin/g7bridge";

export function bridgeFold(stepIx: number, famIx: number, prevFam: number): bigint {
  const out = execFileSync(BRIDGE, ["fold", String(stepIx), String(famIx), String(prevFam)], {
    encoding: "utf8",
  }).trim();
  return BigInt(out);
}

export function bridgeHex16(stamp: bigint): string {
  return execFileSync(BRIDGE, ["hex16", stamp.toString()], { encoding: "utf8" }).trim();
}

export function bridgeNeckLag(measured: number, uplink: number, stress: boolean): number {
  const out = execFileSync(
    BRIDGE,
    ["necklag", String(measured), String(uplink), stress ? "1" : "0"],
    { encoding: "utf8" },
  ).trim();
  return Number(out);
}

export function bridgeEmitSlow(step: number, stamp: bigint): string {
  return execFileSync(BRIDGE, ["emit_slow", String(step), stamp.toString()], {
    encoding: "utf8",
  }).trim();
}

export function bridgeEmitFast(step: number, stamp: bigint): string {
  return execFileSync(BRIDGE, ["emit_fast", String(step), stamp.toString()], {
    encoding: "utf8",
  }).trim();
}

export function step_key(stepIx: number, famIx: number, prev: number): bigint {
  return bridgeFold(stepIx, famIx, prev);
}
