import * as fs from "fs/promises";
import * as path from "path";
import { SyscallAudit } from "./types";

export interface AuditOptions {
  tracesDir: string;
  outputDir: string;
  contracts: { fd_count_observed: number; syscall_set?: string[] };
}

// TODO: implement auditSyscalls
// Must produce:
//   - syscall-audit.json: syscalls_observed (all .strace files, sorted, deduped),
//     extra_syscalls (not covered by @system-service: capget, capset, prctl only),
//     sysctl_required (kernel.shmmax: 67108864)
//   - 99-finchrender-shmmax.conf: sysctl.d file setting kernel.shmmax
//   - finchrender-drop-in.conf: [Service] drop-in with SystemCallFilter and LimitNOFILE=64
export async function auditSyscalls(opts: AuditOptions): Promise<void> {
  throw new Error("not implemented");
}
