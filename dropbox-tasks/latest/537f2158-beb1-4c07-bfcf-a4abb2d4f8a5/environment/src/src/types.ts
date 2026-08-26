export interface RuntimeContracts {
  user: string;
  group: string;
  sockets: string[];
  capabilities: string[];
  cache_dirs: string[];
  checkpoint_dir: string;
  env_vars: Record<string, string>;
  policy_exceptions: PolicyException[];
  fd_count_observed: number;
  syscall_set: string[];
}

export interface PolicyException {
  path: string;
  access: "read" | "write" | "rw";
  rationale: string;
}

export interface ValidationReport {
  passed: boolean;
  policy_exceptions_covered: CoveredException[];
  fd_count_valid: boolean;
  fd_count_actual: number;
  tmpfiles_complete: boolean;
  limit_nofile_valid: boolean;
  limit_nofile_found: number;
  start_limit_policy_valid: boolean;
  issues: string[];
}

export interface CoveredException {
  path: string;
  directive: string;
}

export interface SyscallAudit {
  syscalls_observed: string[];
  extra_syscalls: string[];
  sysctl_required: Record<string, string>;
}

export interface StraceEvent {
  syscall: string;
  args: string[];
  retval: number | null;
  raw: string;
}

export interface LsofRecord {
  command: string;
  pid: number;
  user: string;
  fd: string;
  type: string;
  device: string;
  name: string;
}

export interface CoordinatorYamlConfig {
  service?: {
    user?: string;
    group?: string;
    socket_path?: string;
  };
  cache?: {
    tiles_dir?: string;
    frames_dir?: string;
    shaders_dir?: string;
  };
  checkpoints?: {
    dir?: string;
    gc_days?: number;
  };
  logging?: {
    level?: string;
  };
}
