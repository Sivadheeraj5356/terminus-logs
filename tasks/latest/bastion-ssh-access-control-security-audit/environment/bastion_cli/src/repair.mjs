import { chmod, mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { readFileSync } from "node:fs";
import {
  canonicalManifestPayload,
  canonicalManifestPayloadWrapped,
  sha256Hex,
  sortChanges,
} from "./util.mjs";
import { runAudit } from "./audit.mjs";

async function writeModes(stagingRoot, fileModes) {
  for (const [rel, mode] of Object.entries(fileModes)) {
    if (!rel.includes("/")) continue;
    const full = join(stagingRoot, rel);
    await mkdir(dirname(full), { recursive: true });
    const modeNum = parseInt(String(mode), 8);
    await chmod(full, modeNum);
  }
}

export async function runRepair(stagingRoot, registry) {
  const changes = [];

  for (const [user, keyLine] of Object.entries(registry.sshKeys)) {
    const rel = `homes/${user}/.ssh/authorized_keys`;
    const full = join(stagingRoot, rel);
    const before = readFileSync(full, "utf8");
    const after = `${keyLine.trim()}\n`;
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, after, "utf8");
    changes.push({
      path: rel,
      before_sha256: sha256Hex(before),
      after_sha256: sha256Hex(after),
    });
  }

  for (const [rel, expectedMap] of Object.entries(registry.sshdSettings)) {
    const full = join(stagingRoot, rel);
    const before = readFileSync(full, "utf8");
    const lines = Object.entries(expectedMap).map(([k, v]) => `${k} ${v}`);
    const after = `${lines.join("\n")}\n`;
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, after, "utf8");
    changes.push({
      path: rel,
      before_sha256: sha256Hex(before),
      after_sha256: sha256Hex(after),
    });
  }

  const sudoPath = join(stagingRoot, "sudoers.d/bastion-users");
  const beforeSudo = readFileSync(sudoPath, "utf8");
  const sudoLines = Object.values(registry.sudoersLines).sort();
  const afterSudo = `${sudoLines.join("\n")}\n`;
  await mkdir(dirname(sudoPath), { recursive: true });
  await writeFile(sudoPath, afterSudo, "utf8");
  changes.push({
    path: "sudoers.d/bastion-users",
    before_sha256: sha256Hex(beforeSudo),
    after_sha256: sha256Hex(afterSudo),
  });

  await writeModes(stagingRoot, registry.fileModes);

  const sorted = sortChanges(changes);
  return {
    staging_root: stagingRoot,
    tenant: registry.tenant,
    changes: changes,
    noop: changes.length === 0,
    manifest_sha256: sha256Hex(canonicalManifestPayloadWrapped(sorted)),
  };
}

export async function repairIfNeeded(stagingRoot, registry) {
  const audit = await runAudit(stagingRoot, registry);
  if (audit.clean) {
    return {
      staging_root: stagingRoot,
      tenant: registry.tenant,
      changes: [],
      noop: true,
      manifest_sha256: sha256Hex(canonicalManifestPayload([])),
    };
  }
  return runRepair(stagingRoot, registry);
}
