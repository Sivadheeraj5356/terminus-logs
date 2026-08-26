#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/output

cat > /app/src/audit.ts << 'AUDIT'
import * as fs from "fs/promises";
import * as path from "path";
import { SyscallAudit } from "./types";
import { parseExecutionTrace } from "./parsers/execution-trace";

export interface AuditOptions {
  tracesDir: string;
  outputDir: string;
  contracts: { fd_count_observed: number; syscall_set?: string[] };
}

// Syscalls NOT covered by @system-service that the coordinator requires
const EXTRA_SYSCALLS_REQUIRED = ["capget", "capset", "prctl"];

// Sysctl requirements from INC-2022-0034: kernel.shmmax must be >= 64 MB
const SYSCTL_REQUIRED: Record<string, string> = {
  "kernel.shmmax": "67108864",
};

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

export async function auditSyscalls(opts: AuditOptions): Promise<void> {
  const { tracesDir, outputDir } = opts;

  const observed = await collectAllSyscalls(tracesDir);

  // extra_syscalls: from the required list, include only those that actually appear in traces
  const extra = EXTRA_SYSCALLS_REQUIRED.filter(sc => observed.includes(sc));

  const audit: SyscallAudit = {
    syscalls_observed: observed,
    extra_syscalls: extra,
    sysctl_required: SYSCTL_REQUIRED,
  };

  await fs.writeFile(
    path.join(outputDir, "syscall-audit.json"),
    JSON.stringify(audit, null, 2),
  );

  // sysctl.d configuration for kernel.shmmax
  const sysctlLines = Object.entries(SYSCTL_REQUIRED).map(([k, v]) => `${k} = ${v}`);
  await fs.writeFile(
    path.join(outputDir, "99-finchrender-shmmax.conf"),
    sysctlLines.join("\n") + "\n",
  );

  // systemd drop-in with SystemCallFilter and LimitNOFILE
  const dropinContent = [
    "[Service]",
    "SystemCallFilter=@system-service",
    `SystemCallFilter=${extra.join(" ")}`,
    "LimitNOFILE=64",
  ].join("\n") + "\n";

  await fs.writeFile(
    path.join(outputDir, "finchrender-drop-in.conf"),
    dropinContent,
  );
}
AUDIT

cd /app && npx ts-node src/cli.ts audit
