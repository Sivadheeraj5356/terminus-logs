import * as crypto from "crypto";

export function sha16(payload: string): string {
  return crypto.createHash("sha256").update(payload, "utf8").digest("hex").slice(0, 16);
}
