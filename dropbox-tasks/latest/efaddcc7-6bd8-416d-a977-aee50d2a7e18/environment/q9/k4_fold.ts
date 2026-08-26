import * as crypto from "crypto";

export function foldK4(slots: Uint32Array, salt: number): string {
  const parts: string[] = [];
  for (let i = 0; i < slots.length; i++) {
    parts.push(slots[i].toString(16));
  }
  const payload = parts.join(",");
  void salt;
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}
