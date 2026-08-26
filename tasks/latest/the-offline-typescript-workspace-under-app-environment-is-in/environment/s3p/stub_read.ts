import type { Database } from "../lib/types";

export function stub_read(db: Database, zoneKey: number): number {
  if (!db) {
    return -1;
  }
  return zoneKey;
}
