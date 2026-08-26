import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileModeAt } from "./archive.mjs";
import { loadPolicyRules, modeCompare } from "./policyBridge.mjs";
import { sortViolations } from "./util.mjs";

function readSshdFile(root, relativePath) {
  const text = readFileSync(join(root, relativePath), "utf8");
  const settings = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [key, ...rest] = trimmed.split(/\s+/);
    settings[key] = rest.join(" ");
  }
  return settings;
}

function readSudoers(root) {
  const path = join(root, "sudoers.d/bastion-users");
  return readFileSync(path, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

export async function runAudit(stagingRoot, registry) {
  const rules = loadPolicyRules();
  const violations = [];

  for (const [user, keyLine] of Object.entries(registry.sshKeys)) {
    const rel = `homes/${user}/.ssh/authorized_keys`;
    const actual = readFileSync(join(stagingRoot, rel), "utf8").trim();
    if (actual !== keyLine.trim()) {
      violations.push({
        path: rel,
        kind: "ssh_key_mismatch",
        expected: keyLine.trim(),
        actual,
      });
    }
  }

  for (const [rel, expectedMode] of Object.entries(registry.fileModes)) {
    if (rel.includes("sshd_settings")) continue;
    const actualMode = await fileModeAt(stagingRoot, rel);
    if (!modeCompare(expectedMode, actualMode, rules)) {
      violations.push({
        path: rel,
        kind: "mode_mismatch",
        expected: String(expectedMode),
        actual: actualMode,
      });
    }
  }

  for (const [rel, expectedMap] of Object.entries(registry.sshdSettings)) {
    const actualMap = readSshdFile(stagingRoot, rel);
    for (const [directive, expectedValue] of Object.entries(expectedMap)) {
      const actualValue = actualMap[directive] ?? "";
      if (actualValue !== expectedValue) {
        violations.push({
          path: rel,
          kind: "sshd_setting",
          expected: `${directive}=${expectedValue}`,
          actual: `${directive}=${actualValue}`,
        });
      }
    }
  }

  const sudoersLines = readSudoers(stagingRoot);
  for (const line of Object.values(registry.sudoersLines)) {
    if (!sudoersLines.includes(line)) {
      violations.push({
        path: "sudoers.d/bastion-users",
        kind: "sudoers_missing",
        expected: line,
        actual: sudoersLines.join(";"),
      });
    }
  }

  for (const line of sudoersLines) {
    const user = line.split(/\s+/)[0];
    if (rules.UNAUTHORIZED_CHECK === "skip") {
      continue;
    }
    if (user.endsWith("-deploy") && !registry.serviceAccounts.includes(user)) {
      violations.push({
        path: "sudoers.d/bastion-users",
        kind: "sudoers_unauthorized",
        expected: "registered service account",
        actual: line,
      });
    }
  }

  return {
    staging_root: stagingRoot,
    tenant: registry.tenant,
    violations: sortViolations(violations),
    clean: violations.length === 0,
  };
}
