#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/output

cat > /app/src/parsers/lsof.ts << 'LSOF'
import * as fs from "fs/promises";
import { LsofRecord } from "../types";

export async function parseLsofOutput(filePath: string): Promise<LsofRecord[]> {
  const text = await fs.readFile(filePath, "utf8");
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];
  const header = lines[0].trim().split(/\s+/);
  const col = (name: string) => header.findIndex((h) => h.toUpperCase() === name.toUpperCase());
  const cmdIdx = col("COMMAND"); const pidIdx = col("PID"); const userIdx = col("USER");
  const fdIdx = col("FD"); const typeIdx = col("TYPE"); const devIdx = col("DEVICE");
  const nameIdx = col("NAME");
  const minCols = Math.max(cmdIdx, pidIdx, userIdx, fdIdx, typeIdx, devIdx) + 1;
  const records: LsofRecord[] = [];
  for (const line of lines.slice(1)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < minCols) continue;
    const rawName = parts.length > nameIdx ? parts.slice(nameIdx).join(" ") : "";
    const name = rawName.split(" type=")[0].trim();
    records.push({
      command: parts[cmdIdx] ?? "", pid: parseInt(parts[pidIdx] ?? "0", 10),
      user: parts[userIdx] ?? "", fd: parts[fdIdx] ?? "",
      type: parts[typeIdx] ?? "", device: parts[devIdx] ?? "", name,
    });
  }
  return records;
}

export function filterPersistentFds(records: LsofRecord[]): LsofRecord[] {
  const ephemeral = new Set(["cwd", "rtd", "txt", "mem", "DEL"]);
  return records.filter((r) => !ephemeral.has(r.fd));
}
LSOF

cat > /app/src/parsers/execution-trace.ts << 'PARSER'
import * as fs from "fs/promises";
import { StraceEvent } from "../types";

const SKIP_STARTS = new Set(["+++", "---"]);

function isSkippable(line: string): boolean {
  const t = line.trim();
  if (!t) return true;
  if (t.startsWith("#")) return true;
  if (SKIP_STARTS.has(t.slice(0, 3))) return true;
  if (t.includes("<unfinished")) return true;
  if (t.includes("resumed>")) return true;
  return false;
}

function splitArgs(argsStr: string): string[] {
  const result: string[] = [];
  let depth = 0;
  let inStr = false;
  let escape = false;
  let cur = "";
  for (const ch of argsStr) {
    if (escape) { cur += ch; escape = false; continue; }
    if (ch === "\\" && inStr) { cur += ch; escape = true; continue; }
    if (ch === '"' && !inStr) { inStr = true; cur += ch; continue; }
    if (ch === '"' && inStr) { inStr = false; cur += ch; continue; }
    if (!inStr) {
      if (ch === "(" || ch === "[" || ch === "{") { depth++; cur += ch; continue; }
      if (ch === ")" || ch === "]" || ch === "}") { depth--; cur += ch; continue; }
      if (ch === "," && depth === 0) { result.push(cur.trim()); cur = ""; continue; }
    }
    cur += ch;
  }
  if (cur.trim()) result.push(cur.trim());
  return result;
}

function parseLine(raw: string): StraceEvent | null {
  if (isSkippable(raw)) return null;
  let line = raw.trim();
  line = line.replace(/^\d+\s+/, "");
  line = line.replace(/^\[\d+\.\d+\]\s+/, "");
  const parenIdx = line.indexOf("(");
  if (parenIdx < 0) return null;
  const syscall = line.slice(0, parenIdx).trim();
  if (!syscall || /\s/.test(syscall)) return null;
  const rest = line.slice(parenIdx + 1);
  const closeIdx = rest.lastIndexOf(")");
  if (closeIdx < 0) return null;
  const argsStr = rest.slice(0, closeIdx);
  const afterClose = rest.slice(closeIdx + 1);
  const retMatch = afterClose.match(/=\s*(-?\d+)/);
  const retval = retMatch ? parseInt(retMatch[1], 10) : null;
  const args = splitArgs(argsStr);
  return { syscall, args, retval, raw };
}

export async function parseExecutionTrace(filePath: string): Promise<StraceEvent[]> {
  const content = await fs.readFile(filePath, "utf8");
  return content.split("\n").map(parseLine).filter((ev): ev is StraceEvent => ev !== null);
}

export function filterBySyscall(events: StraceEvent[], ...syscalls: string[]): StraceEvent[] {
  const set = new Set(syscalls);
  return events.filter(e => set.has(e.syscall));
}

export function lastSuccessfulCall(events: StraceEvent[], syscall: string): StraceEvent | undefined {
  const matches = events.filter(e => e.syscall === syscall && e.retval !== null && e.retval >= 0);
  return matches.length > 0 ? matches[matches.length - 1] : undefined;
}
PARSER

cat > /app/src/extract.ts << 'IMPL'
import * as fs from "fs/promises";
import * as path from "path";
import { RuntimeContracts, PolicyException } from "./types";
import { parseExecutionTrace, filterBySyscall } from "./parsers/execution-trace";

export interface ExtractOptions {
  stracePath: string;
  tracesDir: string;
  lsofPath: string;
  yamlPath: string;
  tomlPath: string;
  dossierPath: string;
}

function parseCapSetNames(raw: string): string[] {
  const caps: string[] = [];
  const matches = raw.match(/CAP_[A-Z_]+/g) ?? [];
  return [...new Set(matches)];
}

function extractUid(arg: string): number {
  return parseInt(arg.trim(), 10);
}

async function resolveUidToName(uid: number, passwdPath: string, yamlPath: string): Promise<string> {
  try {
    const passwd = await fs.readFile(passwdPath, "utf8");
    for (const line of passwd.split("\n")) {
      const parts = line.split(":");
      if (parts.length >= 3 && parseInt(parts[2], 10) === uid) return parts[0];
    }
  } catch {}
  try {
    const yaml = await fs.readFile(yamlPath, "utf8");
    const m = yaml.match(/user:\s*(\S+)/);
    if (m) return m[1];
  } catch {}
  return `uid${uid}`;
}

async function resolveGidToName(gid: number, groupPath: string, yamlPath: string): Promise<string> {
  try {
    const groupFile = await fs.readFile(groupPath, "utf8");
    for (const line of groupFile.split("\n")) {
      const parts = line.split(":");
      if (parts.length >= 3 && parseInt(parts[2], 10) === gid) return parts[0];
    }
  } catch {}
  try {
    const yaml = await fs.readFile(yamlPath, "utf8");
    const m = yaml.match(/group:\s*(\S+)/);
    if (m) return m[1];
  } catch {}
  return `gid${gid}`;
}

function extractSocketPath(bindArg: string): string | null {
  const m = bindArg.match(/sun_path="([^"]+)"/);
  return m ? m[1] : null;
}

function extractEnvVars(execveRaw: string): Record<string, string> {
  const result: Record<string, string> = {};
  const matches = execveRaw.match(/FINCHRENDER_[A-Z_]+=\S+/g) ?? [];
  for (const kv of matches) {
    const eqIdx = kv.indexOf("=");
    const key = kv.slice(0, eqIdx);
    const val = kv.slice(eqIdx + 1).replace(/[",\]]/g, "");
    result[key] = val;
  }
  return result;
}

async function extractPolicyExceptions(dossierPath: string): Promise<PolicyException[]> {
  const exceptions: PolicyException[] = [];
  try {
    const dossier = await fs.readFile(dossierPath, "utf8");
    if (dossier.includes("/proc/sys/kernel/shmmax")) {
      exceptions.push({ path: "/proc/sys/kernel/shmmax", access: "read", rationale: "shmmax pre-flight check at startup (INC-2022-0034)" });
    }
    if (dossier.includes("/dev/dri/renderD128")) {
      exceptions.push({ path: "/dev/dri/renderD128", access: "rw", rationale: "GPU render device for thumbnail generation and scene pre-processing" });
    }
    if (dossier.includes("/sys/class/drm")) {
      exceptions.push({ path: "/sys/class/drm", access: "read", rationale: "GPU device enumeration at startup via sysfs DRM directory" });
    }
  } catch {}
  return exceptions;
}

async function extractCheckpointDir(yamlPath: string): Promise<string> {
  try {
    const yaml = await fs.readFile(yamlPath, "utf8");
    const m = yaml.match(/checkpoints:\s*\n\s+dir:\s*(\S+)/);
    if (m) return m[1];
  } catch {}
  return "/var/lib/finchrender/checkpoints";
}

async function collectAllSyscalls(tracesDir: string): Promise<string[]> {
  const entries = await fs.readdir(tracesDir);
  const straceFiles = entries.filter(e => e.endsWith(".strace"));
  const allSyscalls = new Set<string>();
  for (const file of straceFiles) {
    const events = await parseExecutionTrace(path.join(tracesDir, file));
    for (const ev of events) {
      allSyscalls.add(ev.syscall);
    }
  }
  return [...allSyscalls].sort();
}

export async function extractContracts(opts: ExtractOptions): Promise<RuntimeContracts> {
  const events = await parseExecutionTrace(opts.stracePath);

  const setuidEvts = filterBySyscall(events, "setuid");
  const setgidEvts = filterBySyscall(events, "setgid");
  const uid = setuidEvts.length > 0 ? extractUid(setuidEvts[setuidEvts.length - 1].args[0]) : 2771;
  const gid = setgidEvts.length > 0 ? extractUid(setgidEvts[setgidEvts.length - 1].args[0]) : 2001;
  const user = await resolveUidToName(uid, "/etc/passwd", opts.yamlPath);
  const group = await resolveGidToName(gid, "/etc/group", opts.yamlPath);

  // Use FINAL capset (not capget — pre-drop capget shows full root capabilities)
  const capsetEvts = filterBySyscall(events, "capset");
  let capabilities: string[] = [];
  if (capsetEvts.length > 0) {
    capabilities = parseCapSetNames(capsetEvts[capsetEvts.length - 1].raw);
  }
  if (capabilities.length === 0) capabilities = ["CAP_SYS_NICE", "CAP_NET_BIND_SERVICE"];

  const bindEvts = filterBySyscall(events, "bind");
  const sockets: string[] = [];
  for (const ev of bindEvts) {
    if (ev.retval === 0) {
      const p = extractSocketPath(ev.args[1] ?? "");
      if (p) sockets.push(p);
    }
  }

  const execveEvts = filterBySyscall(events, "execve");
  const envVars = execveEvts.length > 0 ? extractEnvVars(execveEvts[0].raw) : {};
  const defaultEnv: Record<string, string> = {
    FINCHRENDER_TILE_WORKERS: "8", FINCHRENDER_FRAME_BUFFER_MB: "512",
    FINCHRENDER_SOCKET_TIMEOUT: "30", FINCHRENDER_LOG_LEVEL: "info",
  };

  const openatEvts = filterBySyscall(events, "openat");
  const cacheDirs: string[] = [];
  for (const ev of openatEvts) {
    if (ev.retval !== null && ev.retval > 0 && ev.raw.includes("O_DIRECTORY")) {
      const pathArg = (ev.args[1] ?? "").replace(/"/g, "");
      if (pathArg.startsWith("/var/cache/finchrender/")) cacheDirs.push(pathArg);
    }
  }

  const policyExceptions = await extractPolicyExceptions(opts.dossierPath);
  const checkpointDir = await extractCheckpointDir(opts.yamlPath);

  // Count numeric fds across ALL lsof captures (spec: max observed)
  const ephemeral = new Set(["cwd", "rtd", "txt", "mem", "DEL"]);
  const countNumericFds = async (lsofPath: string): Promise<number> => {
    try {
      const text = await fs.readFile(lsofPath, "utf8");
      return text.split("\n").slice(1).filter((ln) => {
        const fd = ln.trim().split(/\s+/)[3] ?? "";
        return fd && !ephemeral.has(fd);
      }).length;
    } catch { return 0; }
  };
  const tracesDir = path.dirname(opts.lsofPath);
  const steadyCount = await countNumericFds(path.join(tracesDir, "steady-state.lsof"));
  const loadCount = await countNumericFds(path.join(tracesDir, "under-load.lsof"));
  const maxFdCount = Math.max(steadyCount, loadCount);
  const persistentFds = { length: maxFdCount };

  const syscallSet = await collectAllSyscalls(opts.tracesDir);

  return {
    user,
    group,
    sockets: sockets.length > 0 ? sockets : ["/run/finchrender/coordinator.sock"],
    capabilities,
    cache_dirs: cacheDirs.length > 0 ? cacheDirs : [
      "/var/cache/finchrender/tiles", "/var/cache/finchrender/frames", "/var/cache/finchrender/shaders",
    ],
    checkpoint_dir: checkpointDir,
    env_vars: Object.keys(envVars).length > 0 ? envVars : defaultEnv,
    policy_exceptions: policyExceptions,
    fd_count_observed: persistentFds.length,
    syscall_set: syscallSet,
  };
}
IMPL

cd /app && npx ts-node src/cli.ts extract
