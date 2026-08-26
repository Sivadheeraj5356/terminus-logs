import { StraceEvent } from "../types";

export interface TraceReadOptions {
  pid?: number;
  syscalls?: string[];
}

export async function parseStraceLog(
  filePath: string,
  _opts?: TraceReadOptions
): Promise<StraceEvent[]> {
  throw new Error("parseStraceLog: not implemented");
}

export function filterBySyscall(
  events: StraceEvent[],
  ...syscalls: string[]
): StraceEvent[] {
  throw new Error("filterBySyscall: not implemented");
}

export function lastSuccessfulCall(
  events: StraceEvent[],
  syscall: string
): StraceEvent | undefined {
  throw new Error("lastSuccessfulCall: not implemented");
}
