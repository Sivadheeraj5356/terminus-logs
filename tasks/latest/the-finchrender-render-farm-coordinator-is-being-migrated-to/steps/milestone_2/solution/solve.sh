#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/output

cat > /app/src/writers/unit.ts << 'UNIT'
import { RuntimeContracts } from "../types";

export function writeUnitFile(contracts: RuntimeContracts): string {
  const caps = contracts.capabilities.join(" ");
  const devLines = contracts.policy_exceptions
    .filter(e => e.path.startsWith("/dev/"))
    .map(e => `DeviceAllow=${e.path} ${e.access === "read" ? "r" : e.access === "write" ? "w" : "rw"}`)
    .join("\n");
  const checkpointBase = contracts.checkpoint_dir.split("/").slice(0, -1).join("/") || contracts.checkpoint_dir;
  return `[Unit]
Description=FinchRender Render Farm Coordinator
Requires=finchrender.socket
After=finchrender.socket network.target systemd-tmpfiles-setup.service local-fs.target udev-settle.service

[Service]
Type=exec
User=${contracts.user}
Group=${contracts.group}
EnvironmentFile=/etc/finchrender/finchrender.env
ExecStart=/usr/local/bin/finchrender-coordinator --config /etc/finchrender/coordinator.yaml --system /etc/finchrender/system.toml
Restart=on-failure
RestartSec=5s
StartLimitBurst=5
StartLimitIntervalSec=10min
TimeoutStartSec=30s
TimeoutStopSec=30s
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
RestrictAddressFamilies=AF_UNIX
LockPersonality=yes
RemoveIPC=yes
CapabilityBoundingSet=${caps}
AmbientCapabilities=${caps}
DevicePolicy=closed
${devLines}
ReadWritePaths=/var/cache/finchrender /var/lib/finchrender /var/log/finchrender
LimitNOFILE=64
SystemCallFilter=@system-service
SystemCallFilter=capget capset prctl
MemoryMax=4G

[Install]
WantedBy=multi-user.target
`;
}
UNIT

cat > /app/src/writers/socket.ts << 'SOCK'
import { RuntimeContracts } from "../types";

export function writeSocketFile(contracts: RuntimeContracts): string {
  const socketPath = contracts.sockets[0] ?? "/run/finchrender/coordinator.sock";
  return `[Unit]
Description=FinchRender Coordinator Socket

[Socket]
ListenStream=${socketPath}
SocketUser=${contracts.user}
SocketGroup=${contracts.group}
SocketMode=0660
Accept=no
Backlog=128
DirectoryMode=0755

[Install]
WantedBy=sockets.target
`;
}
SOCK

cat > /app/src/writers/tmpfiles.ts << 'TMPF'
import { RuntimeContracts } from "../types";

export function writeTmpfilesConf(contracts: RuntimeContracts): string {
  const u = contracts.user;
  const g = contracts.group;
  const lines: string[] = [`d  /run/finchrender  0755  ${u}  ${g}  -`];
  for (const dir of contracts.cache_dirs) {
    lines.push(`D  ${dir}  0750  ${u}  ${g}  -`);
  }
  return lines.join("\n") + "\n";
}
TMPF

cat > /app/src/writers/envfile.ts << 'ENV'
import { RuntimeContracts } from "../types";

export function writeEnvFile(contracts: RuntimeContracts): string {
  return Object.entries(contracts.env_vars).map(([k, v]) => `${k}=${v}`).join("\n") + "\n";
}
ENV

cat > /app/src/generate.ts << 'GEN'
import * as fs from "fs/promises";
import * as path from "path";
import { RuntimeContracts } from "./types";
import { writeUnitFile } from "./writers/unit";
import { writeSocketFile } from "./writers/socket";
import { writeTmpfilesConf } from "./writers/tmpfiles";
import { writeEnvFile } from "./writers/envfile";

export interface GenerateOptions {
  contracts: RuntimeContracts;
  outputDir: string;
}

export async function generateSystemdConfig(opts: GenerateOptions): Promise<void> {
  const { contracts, outputDir } = opts;
  await fs.mkdir(outputDir, { recursive: true });
  await fs.writeFile(path.join(outputDir, "finchrender.service"), writeUnitFile(contracts));
  await fs.writeFile(path.join(outputDir, "finchrender.socket"), writeSocketFile(contracts));
  await fs.writeFile(path.join(outputDir, "finchrender-tmpfiles.conf"), writeTmpfilesConf(contracts));
  await fs.writeFile(path.join(outputDir, "finchrender.env"), writeEnvFile(contracts));
}
GEN

cd /app && npx ts-node src/cli.ts generate
