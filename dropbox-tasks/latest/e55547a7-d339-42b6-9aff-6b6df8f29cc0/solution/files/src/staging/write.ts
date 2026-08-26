import * as fs from "fs";
import * as crypto from "crypto";
import { StagingEnvelope, Manifest, Body, FlareEvent } from "../types";

function canonicalStringify(v: unknown): string {
  if (v === null || v === undefined) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return JSON.stringify(v);
  if (typeof v === "string") return JSON.stringify(v);
  if (Array.isArray(v)) {
    return "[" + v.map(canonicalStringify).join(",") + "]";
  }
  const obj = v as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => `${JSON.stringify(k)}:${canonicalStringify(obj[k])}`);
  return "{" + parts.join(",") + "}";
}

export function payloadHash(v: unknown): string {
  const body = canonicalStringify(v);
  return crypto.createHash("sha256").update(body).digest("hex");
}

export function writeStagingEnvelope(
  outPath: string,
  manifest: Manifest,
  bodies: Body[],
  flares: FlareEvent[],
  catalogFingerprint: string,
): StagingEnvelope {
  const envelope: StagingEnvelope = {
    mission_slot: manifest.mission_slot,
    manifest,
    bodies,
    flares,
    catalog_fingerprint: catalogFingerprint,
    staging_hash: "",
  };
  envelope.staging_hash = payloadHash(envelope);
  fs.writeFileSync(outPath, JSON.stringify(envelope, null, 2));
  return envelope;
}
