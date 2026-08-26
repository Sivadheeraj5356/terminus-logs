import * as fs from "fs/promises";
import { RuntimeContracts, PolicyException } from "./types";
import { parseExecutionTrace, filterBySyscall } from "./parsers/execution-trace";
import { parseLsofOutput, filterPersistentFds } from "./parsers/lsof";

export interface ExtractOptions {
  stracePath: string;
  tracesDir: string;
  lsofPath: string;
  yamlPath: string;
  tomlPath: string;
  dossierPath: string;
}

// TODO: implement extractContracts
// Must populate all RuntimeContracts fields including:
//   - capabilities: from the FINAL capset call only (not capget pre-drop values)
//   - checkpoint_dir: from checkpoints.dir in coordinator.yaml
//   - syscall_set: from ALL .strace files in tracesDir, sorted and deduplicated
//   - env_vars: only FINCHRENDER_* keys from execve envp
export async function extractContracts(opts: ExtractOptions): Promise<RuntimeContracts> {
  throw new Error("not implemented");
}
