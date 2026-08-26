import * as fs from "fs/promises";
import { StraceEvent } from "../types";

const SKIP_MARKERS = new Set(["+++", "---", "<.."]);

function isSkippable(trimmed: string): boolean {
  return SKIP_MARKERS.has(trimmed.slice(0, 3));
}

function splitArgs(argsStr: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let inStr = false;
  let cur = "";

  for (const ch of argsStr) {
    if (ch === '"' && depth === 0) {
      inStr = !inStr;
      cur += ch;
      continue;
    }
    if (inStr) {
      cur += ch;
      continue;
    }
    if (ch === "{" || ch === "[") depth++;
    else if (ch === "}" || ch === "]") depth--;
    if (ch === "," && depth === 0) {
      parts.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }

  if (cur.trim()) parts.push(cur.trim());
  return parts;
}

function parseLine(raw: string): StraceEvent | null {
  const trimmed = raw.trim();
  if (!trimmed || isSkippable(trimmed)) return null;

  const normalized = trimmed
    .replace(/^\d+\s+/, "")
    .replace(/^\d+\.\d+\s+/, "");

  const parenAt = normalized.indexOf("(");
  if (parenAt === -1) return null;

  const syscall = normalized.slice(0, parenAt).trim();
  if (!syscall || syscall.includes(" ")) return null;

  const body = normalized.slice(parenAt + 1);
  const closeAt = body.lastIndexOf(")");
  if (closeAt === -1) return null;

  const trailer = body.slice(closeAt + 1);
  const eqAt = trailer.indexOf("=");

  let retval: number | null = null;
  if (eqAt !== -1) {
    const n = parseInt(trailer.slice(eqAt + 1).trim().split(/\s/)[0], 10);
    if (!isNaN(n)) retval = n;
  }

  return { syscall, args: splitArgs(body.slice(0, closeAt)), retval, raw };
}

export async function parseExecutionTrace(filePath: string): Promise<StraceEvent[]> {
  const content = await fs.readFile(filePath, "utf8");
  return content
    .split("\n")
    .map(parseLine)
    .filter((ev): ev is StraceEvent => ev !== null);
}

export function filterBySyscall(
  events: StraceEvent[],
  ...syscalls: string[]
): StraceEvent[] {
  const allowed = new Set(syscalls);
  return events.filter((ev) => allowed.has(ev.syscall));
}

export function lastSuccessfulCall(
  events: StraceEvent[],
  syscall: string
): StraceEvent | undefined {
  return [...events]
    .reverse()
    .find((ev) => ev.syscall === syscall && ev.retval === 0);
}

export function groupBySyscall(
  events: StraceEvent[]
): Map<string, StraceEvent[]> {
  const groups = new Map<string, StraceEvent[]>();
  for (const ev of events) {
    const bucket = groups.get(ev.syscall) ?? [];
    bucket.push(ev);
    groups.set(ev.syscall, bucket);
  }
  return groups;
}
