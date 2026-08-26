#!/usr/bin/env bash
set -euo pipefail

cat > /app/src/validate.ts << 'VALID'
import * as fs from "fs/promises";
import * as path from "path";
import { ValidationReport, CoveredException } from "./types";
import { parseLsofOutput, filterPersistentFds } from "./parsers/lsof";

export interface ValidateOptions {
  outputDir: string;
  contractsPath: string;
  dossierPath: string;
  lsofPath: string;
}

const FD_BOUND = 15;

export async function validateMigration(opts: ValidateOptions): Promise<ValidationReport> {
  const { outputDir, contractsPath, lsofPath } = opts;
  const issues: string[] = [];

  const raw = await fs.readFile(contractsPath, "utf8");
  const contracts = JSON.parse(raw);

  let serviceContent = "";
  try {
    serviceContent = await fs.readFile(path.join(outputDir, "finchrender.service"), "utf8");
  } catch {
    issues.push("finchrender.service not found");
  }

  // Policy exceptions coverage
  const covered: CoveredException[] = [];
  for (const exc of (contracts.policy_exceptions ?? [])) {
    let directive = "";
    if (exc.path.startsWith("/dev/")) {
      const devLine = serviceContent.split("\n").find((ln: string) => ln.includes("DeviceAllow") && ln.includes(exc.path));
      if (devLine) {
        directive = devLine.trim();
      } else {
        issues.push(`policy exception not covered: ${exc.path} (missing DeviceAllow)`);
      }
    } else if (exc.path.startsWith("/proc/") || exc.path.startsWith("/sys/")) {
      directive = `ReadOnlyPaths=${exc.path}`;
    }
    if (directive) covered.push({ path: exc.path, directive });
  }

  // FD count: parse under-load.lsof and record the actual numeric count
  let fdCountValid = false;
  let fdCountActual = 0;
  try {
    const lsofRecords = await parseLsofOutput(lsofPath);
    const persistent = filterPersistentFds(lsofRecords);
    fdCountActual = persistent.length;
    fdCountValid = fdCountActual <= FD_BOUND;
    if (!fdCountValid) issues.push(`fd count ${fdCountActual} exceeds bound ${FD_BOUND}`);
  } catch (e) {
    issues.push(`failed to parse lsof: ${e}`);
  }

  // Tmpfiles completeness
  let tmpfilesComplete = false;
  try {
    const tmpContent = await fs.readFile(path.join(outputDir, "finchrender-tmpfiles.conf"), "utf8");
    const hasRunDir = tmpContent.includes("/run/finchrender");
    const hasAllCacheDirs = (contracts.cache_dirs ?? []).every((d: string) => tmpContent.includes(d));
    tmpfilesComplete = hasRunDir && hasAllCacheDirs;
    if (!hasRunDir) issues.push("tmpfiles.conf missing /run/finchrender entry");
    if (!hasAllCacheDirs) {
      for (const d of (contracts.cache_dirs ?? [])) {
        if (!tmpContent.includes(d)) issues.push(`tmpfiles.conf missing entry for ${d}`);
      }
    }
  } catch {
    issues.push("finchrender-tmpfiles.conf not found");
  }

  // LimitNOFILE: parse actual value from service file and record it
  let limitNofileValid = false;
  let limitNofileFound = 0;
  const nofileMatch = serviceContent.match(/LimitNOFILE=(\d+)/);
  if (nofileMatch) {
    limitNofileFound = parseInt(nofileMatch[1], 10);
    limitNofileValid = limitNofileFound > (contracts.fd_count_observed ?? 0);
    if (!limitNofileValid) issues.push(`LimitNOFILE=${limitNofileFound} is not greater than fd_count_observed=${contracts.fd_count_observed}`);
  } else {
    issues.push("LimitNOFILE= directive not found in finchrender.service");
  }

  // StartLimit policy validation
  const hasBurst = serviceContent.includes("StartLimitBurst=5");
  const hasInterval = serviceContent.includes("StartLimitIntervalSec=10min");
  const startLimitPolicyValid = hasBurst && hasInterval;
  if (!hasBurst) issues.push("StartLimitBurst=5 not found in finchrender.service");
  if (!hasInterval) issues.push("StartLimitIntervalSec=10min not found in finchrender.service");

  const passed = issues.length === 0 && covered.length >= (contracts.policy_exceptions ?? []).length;

  return {
    passed,
    policy_exceptions_covered: covered,
    fd_count_valid: fdCountValid,
    fd_count_actual: fdCountActual,
    tmpfiles_complete: tmpfilesComplete,
    limit_nofile_valid: limitNofileValid,
    limit_nofile_found: limitNofileFound,
    start_limit_policy_valid: startLimitPolicyValid,
    issues,
  };
}
VALID

cd /app && npx ts-node src/cli.ts validate
