import { createHash } from "node:crypto";
import * as fs from "node:fs";

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

function sha256(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

export function canonicalJson(value: JsonValue): string {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key]!)}`).join(",")}}`;
}

function parseObject(text: string): { [key: string]: JsonValue } {
  const value: unknown = JSON.parse(text);
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new Error("expected JSON object");
  }
  return value as { [key: string]: JsonValue };
}

export interface DerivedProvenance {
  journalDigest: string;
  configDigest: string;
  cacheKey: string;
}

export function deriveProvenance(journalPath: string, configPath: string): DerivedProvenance {
  const lines = fs
    .readFileSync(journalPath, "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const seen = new Map<string, string>();
  const eventDigests: string[] = [];
  for (const line of lines) {
    const event = parseObject(line);
    const eventId = event.event_id;
    if (typeof eventId !== "string" || eventId.length === 0) {
      throw new Error("invalid event_id");
    }
    const canonical = canonicalJson(event);
    const prior = seen.get(eventId);
    if (prior !== undefined) {
      if (prior !== canonical) {
        throw new Error(`conflicting event id ${eventId}`);
      }
      continue;
    }
    seen.set(eventId, canonical);
    eventDigests.push(sha256(canonical));
  }
  const config = parseObject(fs.readFileSync(configPath, "utf8"));
  const configDigest = sha256(canonicalJson(config));
  const journalDigest = sha256(eventDigests.join("\n"));
  const cacheKey = sha256(`qpcr-journal-v2\n${journalDigest}`);
  return { journalDigest, configDigest, cacheKey };
}
