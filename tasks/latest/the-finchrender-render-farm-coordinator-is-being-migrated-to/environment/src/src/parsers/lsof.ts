import * as fs from "fs/promises";
import { LsofRecord } from "../types";

export async function parseLsofOutput(path: string): Promise<LsofRecord[]> {
  const text = await fs.readFile(path, "utf8");
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length < 2) return [];

  const header = lines[0].trim().split(/\s+/);
  const col = (name: string) => header.findIndex((h) => h.toUpperCase() === name.toUpperCase());

  const cmdIdx = col("COMMAND");
  const pidIdx = col("PID");
  const userIdx = col("USER");
  const fdIdx = col("FD");
  const typeIdx = col("TYPE");
  const devIdx = col("DEVICE");
  const nameIdx = col("NAME");

  const minCols = Math.max(cmdIdx, pidIdx, userIdx, fdIdx, typeIdx, devIdx) + 1;
  const records: LsofRecord[] = [];
  for (const line of lines.slice(1)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < minCols) continue;
    // NAME column may be absent for unnamed sockets; treat as empty string
    const rawName = parts.length > nameIdx ? parts.slice(nameIdx).join(" ") : "";
    const name = rawName.split(" type=")[0].trim();
    records.push({
      command: parts[cmdIdx] ?? "",
      pid: parseInt(parts[pidIdx] ?? "0", 10),
      user: parts[userIdx] ?? "",
      fd: parts[fdIdx] ?? "",
      type: parts[typeIdx] ?? "",
      device: parts[devIdx] ?? "",
      name,
    });
  }
  return records;
}

export function filterPersistentFds(records: LsofRecord[]): LsofRecord[] {
  const ephemeral = new Set(["cwd", "rtd", "txt", "mem", "DEL"]);
  return records.filter((r) => !ephemeral.has(r.fd));
}
