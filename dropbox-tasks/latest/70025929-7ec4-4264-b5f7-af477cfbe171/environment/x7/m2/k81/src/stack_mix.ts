import { execFileSync } from "node:child_process";

const BRIDGE = process.env.G7_BRIDGE ?? "/app/environment/bin/g7bridge";

export type Vec4 = [number, number, number, number];
export type Storage = [Vec4, Vec4, Vec4];

export interface PackState {
  lastA: bigint;
  lastB: bigint;
  storage: Storage;
  neckTm: number;
  uplinkTm: number;
}

export function freshPack(): PackState {
  return {
    lastA: BigInt("18446744073709551615"),
    lastB: BigInt("18446744073709551615"),
    storage: [
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
    ],
    neckTm: 0,
    uplinkTm: 0,
  };
}

function flattenStorage(s: Storage): string[] {
  const out: string[] = [];
  for (const row of s) {
    for (const v of row) {
      out.push(String(v));
    }
  }
  return out;
}

export function stack_apply(
  pack: PackState,
  tagA: bigint,
  tagB: bigint,
  incoming: Storage,
): Storage {
  const args = [
    "merge_hold",
    pack.lastA.toString(),
    pack.lastB.toString(),
    tagA.toString(),
    tagB.toString(),
    String(pack.neckTm),
    String(pack.uplinkTm),
    ...flattenStorage(incoming),
  ];
  const out = execFileSync(BRIDGE, args, { encoding: "utf8" }).trim().split(",");
  pack.lastA = BigInt(out[0]!);
  pack.lastB = BigInt(out[1]!);
  pack.neckTm = Number(out[2]);
  pack.uplinkTm = Number(out[3]);
  let idx = 4;
  const storage: Storage = [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ];
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 4; c++) {
      storage[r]![c] = Number(out[idx++]);
    }
  }
  pack.storage = storage;
  return storage;
}
