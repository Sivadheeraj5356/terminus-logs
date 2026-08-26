import { createHash } from "crypto";
import type { RowRec } from "../lib/types";

export function hash_box(recs: RowRec[]): string {
  const body = recs.map((r) => r.instanceUid).join("|");
  return createHash("sha256").update(body).digest("hex").slice(0, 16);
}
