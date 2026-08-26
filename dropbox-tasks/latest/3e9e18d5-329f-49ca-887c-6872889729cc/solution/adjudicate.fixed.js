#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const NONWAIVABLE = new Set([
  "critical_vuln",
  "untrusted_signer",
  "weak_slsa",
  "attestation_mismatch",
  "unknown_service",
  "unknown_env",
]);

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + "\n");
}

function loadBundle(inputDir) {
  return {
    policy: readJson(path.join(inputDir, "policy.json")),
    runtime: readJson(path.join(inputDir, "runtime_state.json")),
    tests: readJson(path.join(inputDir, "test_runs.json")),
    exceptions: readJson(path.join(inputDir, "exceptions.json")),
    candidates: readJson(path.join(inputDir, "candidates.json")),
  };
}

function semver(value) {
  return value.split(".").map((part) => Number.parseInt(part, 10));
}

function compareVersion(left, right) {
  const a = semver(left);
  const b = semver(right);
  for (let i = 0; i < 3; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

function versionBonus(candidateVersion, active) {
  if (!active) return 60;
  const cand = semver(candidateVersion);
  const old = semver(active.version);
  const raw =
    Math.max(0, cand[0] - old[0]) * 40 +
    Math.max(0, cand[1] - old[1]) * 8 +
    Math.max(0, cand[2] - old[2]) * 2;
  return Math.min(raw, 60);
}

function hoursBetween(current, builtAt) {
  return (new Date(current).getTime() - new Date(builtAt).getTime()) / 3600000;
}

function notExpired(current, expiresAt) {
  return new Date(expiresAt).getTime() >= new Date(current).getTime();
}

function makeMaps(bundle) {
  const runtime = new Map();
  for (const row of bundle.runtime.active || []) {
    runtime.set(`${row.service}\u0000${row.env}`, row);
  }
  const runs = new Map();
  for (const row of bundle.tests.runs || []) runs.set(row.id, row);
  const windows = new Map();
  for (const row of bundle.policy.windows || []) windows.set(row.id, row);
  return { runtime, runs, windows };
}

function validException(candidate, reason, bundle) {
  const current = bundle.policy.current_time;
  for (const exc of bundle.exceptions.exceptions || []) {
    if (!(candidate.exception_tokens || []).includes(exc.token)) continue;
    if (exc.service !== candidate.service || exc.env !== candidate.env) continue;
    if (exc.reason !== reason) continue;
    if (notExpired(current, exc.expires_at)) return true;
  }
  return false;
}

function evaluateCandidate(candidate, bundle) {
  const policy = bundle.policy;
  const { runtime, runs, windows } = makeMaps(bundle);
  const servicePolicy = policy.services[candidate.service];
  const reasons = new Set();
  const waived = new Set();

  if (!servicePolicy) reasons.add("unknown_service");
  if (!policy.envs[candidate.env]) reasons.add("unknown_env");

  const active = runtime.get(`${candidate.service}\u0000${candidate.env}`);
  if (active) {
    if (compareVersion(candidate.version, active.version) <= 0) reasons.add("not_newer_version");
    if (candidate.digest === active.digest) reasons.add("already_active_digest");
  }

  if (servicePolicy) {
    if (hoursBetween(policy.current_time, candidate.built_at) > servicePolicy.max_age_hours) {
      reasons.add("stale_build");
    }
    const signer = policy.trusted_signers[candidate.signer] || {};
    if (!signer.active || !servicePolicy.allowed_signers.includes(candidate.signer)) {
      reasons.add("untrusted_signer");
    }
    if ((candidate.attestations.slsa_level || 0) < servicePolicy.min_slsa) {
      reasons.add("weak_slsa");
    }
    const run = runs.get(candidate.attestations.test_run_id);
    if (
      !run ||
      run.status !== "passed" ||
      run.digest !== candidate.digest ||
      run.source_ref !== candidate.attestations.source_ref ||
      run.coverage < servicePolicy.min_coverage ||
      run.flaky !== false
    ) {
      reasons.add("attestation_mismatch");
    }
    if ((candidate.sbom || []).some((row) => row.severity === "critical")) {
      reasons.add("critical_vuln");
    }
    if ((candidate.sbom || []).some((row) => servicePolicy.forbidden_licenses.includes(row.license))) {
      reasons.add("forbidden_license");
    }
    for (const flag of servicePolicy.exception_required_for || []) {
      if ((candidate.features || {})[flag] === true) reasons.add("missing_required_exception");
    }
  }

  const window = windows.get(candidate.requested_window);
  if (
    !window ||
    window.env !== candidate.env ||
    new Date(window.starts_at).getTime() <= new Date(policy.current_time).getTime()
  ) {
    reasons.add("outside_window");
  }

  for (const reason of Array.from(reasons)) {
    if (!NONWAIVABLE.has(reason) && validException(candidate, reason, bundle)) {
      reasons.delete(reason);
      waived.add(reason);
    }
  }

  const orderedReasons = policy.reason_order.filter((reason) => reasons.has(reason));
  const orderedWaived = policy.reason_order.filter((reason) => waived.has(reason));
  if (orderedReasons.length > 0) {
    return { eligible: false, reasons: orderedReasons, warnings: orderedWaived };
  }

  let risk = 0;
  for (const row of candidate.sbom || []) {
    if (row.severity !== "critical") {
      risk += policy.risk_weights.vulnerabilities[row.severity] || 0;
    }
  }
  for (const [flag, weight] of Object.entries(policy.risk_weights.features)) {
    if ((candidate.features || {})[flag] === true) risk += weight;
  }
  for (const reason of orderedWaived) {
    risk += policy.risk_weights.waivers[reason] || 0;
  }

  const value = servicePolicy.priority + candidate.rollout_impact + versionBonus(candidate.version, active);
  return {
    eligible: true,
    risk_score: risk,
    deployment_value: value,
    warnings: orderedWaived.map((reason) => `waived:${reason}`),
  };
}

function validPlan(selected, evaluations, bundle) {
  const policy = bundle.policy;
  const windows = new Map(policy.windows.map((row) => [row.id, row]));
  const serviceEnv = new Set();
  const selectedByServiceEnv = new Map();
  const envCounts = new Map();
  const windowCounts = new Map();
  const windowRisk = new Map();
  const windowDb = new Map();

  for (const candidate of selected) {
    const serviceKey = `${candidate.service}\u0000${candidate.env}`;
    if (serviceEnv.has(serviceKey)) return false;
    serviceEnv.add(serviceKey);
    selectedByServiceEnv.set(serviceKey, candidate);

    envCounts.set(candidate.env, (envCounts.get(candidate.env) || 0) + 1);
    const windowId = candidate.requested_window;
    windowCounts.set(windowId, (windowCounts.get(windowId) || 0) + 1);
    windowRisk.set(windowId, (windowRisk.get(windowId) || 0) + evaluations.get(candidate.id).risk_score);
    if ((candidate.features || {}).db_migration === true) {
      windowDb.set(windowId, (windowDb.get(windowId) || 0) + 1);
    }
  }

  for (const candidate of selected) {
    const candidateStart = windows.get(candidate.requested_window).starts_at;
    const visibleRuntime = new Map();
    for (const row of bundle.runtime.active || []) {
      visibleRuntime.set(`${row.service}\u0000${row.env}`, row.version);
    }
    for (const deployed of selected) {
      const deployedStart = windows.get(deployed.requested_window).starts_at;
      if (deployedStart <= candidateStart) {
        visibleRuntime.set(`${deployed.service}\u0000${deployed.env}`, deployed.version);
      }
    }
    for (const requirement of candidate.requires || []) {
      const env = requirement.env || candidate.env;
      const version = visibleRuntime.get(`${requirement.service}\u0000${env}`);
      if (!version || compareVersion(version, requirement.min_version) < 0) return false;
    }
    for (const conflict of candidate.conflicts_with || []) {
      const env = conflict.env || candidate.env;
      if (selectedByServiceEnv.has(`${conflict.service}\u0000${env}`)) return false;
    }
  }

  for (const [env, count] of envCounts.entries()) {
    if (count > policy.envs[env].max_approvals) return false;
  }
  for (const [windowId, count] of windowCounts.entries()) {
    const window = windows.get(windowId);
    if (count > window.capacity) return false;
    if ((windowRisk.get(windowId) || 0) > window.risk_budget) return false;
    if ((windowDb.get(windowId) || 0) > window.max_db_migrations) return false;
  }
  return true;
}

function planBetter(a, b) {
  if (b === null) return true;
  if (a.value !== b.value) return a.value > b.value;
  if (a.risk !== b.risk) return a.risk < b.risk;
  if (a.count !== b.count) return a.count > b.count;
  return a.ids < b.ids;
}

function choosePlan(candidates, evaluations, bundle) {
  const eligible = candidates.filter((candidate) => evaluations.get(candidate.id).eligible);
  let bestKey = null;
  let bestPlan = [];
  const total = 1 << eligible.length;
  for (let mask = 0; mask < total; mask += 1) {
    const plan = [];
    for (let idx = 0; idx < eligible.length; idx += 1) {
      if (mask & (1 << idx)) plan.push(eligible[idx]);
    }
    if (!validPlan(plan, evaluations, bundle)) continue;
    const value = plan.reduce((sum, row) => sum + evaluations.get(row.id).deployment_value, 0);
    const risk = plan.reduce((sum, row) => sum + evaluations.get(row.id).risk_score, 0);
    const ids = plan.map((row) => row.id).sort().join(",");
    const key = { value, risk, count: plan.length, ids };
    if (planBetter(key, bestKey)) {
      bestKey = key;
      bestPlan = plan;
    }
  }
  return bestPlan;
}

function sortedObject(map) {
  const out = {};
  for (const key of Array.from(map.keys()).sort()) out[key] = map.get(key);
  return out;
}

function buildOutput(bundle) {
  const candidates = bundle.candidates.candidates;
  const evaluations = new Map();
  for (const candidate of candidates) {
    evaluations.set(candidate.id, evaluateCandidate(candidate, bundle));
  }

  const selectedCandidates = choosePlan(candidates, evaluations, bundle);
  const selectedIds = new Set(selectedCandidates.map((row) => row.id));
  const selectedServiceEnv = new Set(selectedCandidates.map((row) => `${row.service}\u0000${row.env}`));
  const windows = new Map(bundle.policy.windows.map((row) => [row.id, row]));
  const selected = [];
  const rejected = [];
  const deferred = [];

  for (const candidate of candidates) {
    const ev = evaluations.get(candidate.id);
    if (!ev.eligible) {
      rejected.push({ candidate_id: candidate.id, reasons: ev.reasons });
    } else if (selectedIds.has(candidate.id)) {
      selected.push({
        candidate_id: candidate.id,
        service: candidate.service,
        env: candidate.env,
        window_id: candidate.requested_window,
        deployment_value: ev.deployment_value,
        risk_score: ev.risk_score,
        warnings: ev.warnings,
      });
    } else {
      const reason = selectedServiceEnv.has(`${candidate.service}\u0000${candidate.env}`)
        ? "lower_ranked_candidate"
        : "capacity_or_budget";
      deferred.push({ candidate_id: candidate.id, reasons: [reason] });
    }
  }

  selected.sort((a, b) => {
    const keyA = [a.env, windows.get(a.window_id).starts_at, a.service, a.candidate_id].join("\u0000");
    const keyB = [b.env, windows.get(b.window_id).starts_at, b.service, b.candidate_id].join("\u0000");
    return keyA.localeCompare(keyB);
  });
  rejected.sort((a, b) => a.candidate_id.localeCompare(b.candidate_id));
  deferred.sort((a, b) => a.candidate_id.localeCompare(b.candidate_id));

  const byEnv = new Map();
  const byWindow = new Map();
  for (const row of selected) {
    byEnv.set(row.env, (byEnv.get(row.env) || 0) + 1);
    byWindow.set(row.window_id, (byWindow.get(row.window_id) || 0) + 1);
  }

  return {
    selected,
    deferred,
    rejected,
    summary: {
      selected_count: selected.length,
      deferred_count: deferred.length,
      rejected_count: rejected.length,
      total_value: selected.reduce((sum, row) => sum + row.deployment_value, 0),
      total_risk: selected.reduce((sum, row) => sum + row.risk_score, 0),
      by_env: sortedObject(byEnv),
      by_window: sortedObject(byWindow),
    },
  };
}

function main() {
  const inputDir = process.argv[2] || "/app/task_file/input_data";
  const outputDir = process.argv[3] || "/app/task_file/output_data";
  fs.mkdirSync(outputDir, { recursive: true });
  const output = buildOutput(loadBundle(inputDir));
  writeJson(path.join(outputDir, "deployment_decisions.json"), output);
}

main();
