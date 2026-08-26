import { chmod, mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { readFileSync } from "node:fs";
import { canonicalManifestPayload, sha256Hex, sortChanges } from "./util.mjs";
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

function recordChange(changes, rel, before, after) {
  if (sha256Hex(before) === sha256Hex(after)) {
    return;
  }
  changes.push({
    path: rel,
    before_sha256: sha256Hex(before),
    after_sha256: sha256Hex(after),
  });
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
    recordChange(changes, rel, before, after);
  }

  for (const [rel, expectedMap] of Object.entries(registry.sshdSettings)) {
    const full = join(stagingRoot, rel);
    const before = readFileSync(full, "utf8");
    const lines = Object.entries(expectedMap).map(([k, v]) => `${k} ${v}`);
    const after = `${lines.join("\n")}\n`;
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, after, "utf8");
    recordChange(changes, rel, before, after);
  }

  const sudoPath = join(stagingRoot, "sudoers.d/bastion-users");
  const beforeSudo = readFileSync(sudoPath, "utf8");
  const sudoLines = Object.values(registry.sudoersLines);
  const afterSudo = `${sudoLines.join("\n")}\n`;
  await mkdir(dirname(sudoPath), { recursive: true });
  await writeFile(sudoPath, afterSudo, "utf8");
  recordChange(changes, "sudoers.d/bastion-users", beforeSudo, afterSudo);

  await writeModes(stagingRoot, registry.fileModes);

  const sorted = sortChanges(changes);
  return {
    staging_root: stagingRoot,
    tenant: registry.tenant,
    changes: sorted,
    noop: sorted.length === 0,
    manifest_sha256: sha256Hex(canonicalManifestPayload(sorted)),
  };
}

export async function repairIfNeeded(stagingRoot, registry) {
  const audit = await runAudit(stagingRoot, registry);
  if (audit.clean) {
    const empty = [];
    return {
      staging_root: stagingRoot,
      tenant: registry.tenant,
      changes: empty,
      noop: true,
      manifest_sha256: sha256Hex(canonicalManifestPayload(empty)),
    };
  }
  return runRepair(stagingRoot, registry);
}
