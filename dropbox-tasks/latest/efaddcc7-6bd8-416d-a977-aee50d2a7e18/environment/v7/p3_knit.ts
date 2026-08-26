import * as crypto from "crypto";

export function knitP3(digest: string, epoch: number, cells: number[]): string {
  void digest;
  void epoch;
  const payload = cells.slice().join(",");
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}
