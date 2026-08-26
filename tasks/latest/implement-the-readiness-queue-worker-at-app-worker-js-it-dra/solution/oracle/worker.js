#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";
import * as tf from "@tensorflow/tfjs";

const ROOT = "/app";
const PENDING = path.join(ROOT, "queue/pending");
const DONE = path.join(ROOT, "queue/done");
const OUTPUT = path.join(ROOT, "output/drain_report.json");
const ARTIFACT_ROOT = "/app/mlflow_artifacts";
const TRACKING_URI = process.env.MLFLOW_TRACKING_URI || "http://127.0.0.1:5000";

function configPath(envKey, fallback) {
  return process.env[envKey] || fallback;
}

const contractBootstrap = JSON.parse(
  fs.readFileSync(
    configPath("READINESS_CONTRACT_PATH", "/app/config/readiness_contract.json"),
    "utf8",
  ),
);
const contract = contractBootstrap;
const rules = JSON.parse(
  fs.readFileSync(
    configPath(
      contractBootstrap.config_paths?.rules_env || "READINESS_RULES_PATH",
      contractBootstrap.config_paths?.defaults?.rules || "/app/config/readiness_rules.json",
    ),
    "utf8",
  ),
);
const manifest = JSON.parse(
  fs.readFileSync(
    configPath(
      contractBootstrap.config_paths?.manifest_env || "MLFLOW_MANIFEST_PATH",
      contractBootstrap.config_paths?.defaults?.manifest ||
        "/app/config/mlflow_manifest.json",
    ),
    "utf8",
  ),
);
const weights = JSON.parse(
  fs.readFileSync(
    configPath(
      contractBootstrap.config_paths?.weights_env || "MODEL_WEIGHTS_PATH",
      contractBootstrap.config_paths?.defaults?.weights || "/app/model/weights.json",
    ),
    "utf8",
  ),
);

function parseCpuMillicores(value) {
  if (value == null) return 0;
  const raw = String(value);
  if (raw.endsWith("m")) return Number.parseFloat(raw.slice(0, -1));
  return Number.parseFloat(raw) * 1000;
}

function parseMemoryMib(value) {
  if (value == null) return 0;
  const raw = String(value);
  if (raw.endsWith("Mi")) return Number.parseFloat(raw.slice(0, -2));
  if (raw.endsWith("Gi")) return Number.parseFloat(raw.slice(0, -2)) * 1024;
  return Number.parseFloat(raw) / (1024 * 1024);
}

function bankersRound(value, decimals) {
  const factor = 10 ** decimals;
  const scaled = value * factor;
  const floor = Math.floor(scaled);
  const fraction = scaled - floor;
  if (fraction > 0.5) return Math.ceil(scaled) / factor;
  if (fraction < 0.5) return floor / factor;
  return (floor % 2 === 0 ? floor : floor + 1) / factor;
}

function resolveProfile(profileRef) {
  let resolved = profileRef;
  const seen = new Set();
  while (rules.profile_aliases?.[resolved] && !seen.has(resolved)) {
    seen.add(resolved);
    resolved = rules.profile_aliases[resolved];
  }
  return { profileRef, resolved };
}

function resolveRulesSet(ref, seen = new Set()) {
  if (seen.has(ref)) return { binding_overrides: {} };
  seen.add(ref);
  const rulesSet = rules.rules_sets?.[ref] || rules.rules_sets?.default || {};
  let overrides = { ...(rulesSet.binding_overrides || {}) };
  if (rulesSet.extends) {
    const parent = resolveRulesSet(rulesSet.extends, seen);
    overrides = { ...parent.binding_overrides, ...overrides };
  }
  return { binding_overrides: overrides };
}

function mergeBinding(base, override, featureName) {
  let policy = contract.binding_merge?.policy || "rules_wins";
  const perFeature = contract.binding_merge?.per_feature || {};
  if (featureName && perFeature[featureName]) {
    policy = perFeature[featureName];
  }
  if (policy === "registry_wins") {
    return { ...override, ...base };
  }
  return { ...base, ...override };
}

function mergeStackOverrides(name, stack) {
  const policy =
    contract.rules_stack_merge?.override_policy || "last_wins";
  let merged = {};
  for (const ref of stack) {
    const chunk = resolveRulesSet(ref).binding_overrides?.[name] || {};
    if (policy === "first_wins") {
      for (const [key, value] of Object.entries(chunk)) {
        if (!(key in merged)) merged[key] = value;
      }
    } else {
      merged = { ...merged, ...chunk };
    }
  }
  return merged;
}

function bindingOverridesForJob(name, job) {
  const precedence = contract.rules_selection?.precedence || "ref_default";
  const stack = job.rules_profile_stack;
  if (stack?.length && precedence === "stack_over_ref") {
    return mergeStackOverrides(name, stack);
  }
  if (stack?.length) {
    return mergeStackOverrides(name, stack);
  }
  const rulesRef = job.rules_ref || "default";
  return resolveRulesSet(rulesRef).binding_overrides?.[name] || {};
}

function bindingSpec(name, job) {
  const base = { ...contract.bindings[name] };
  const override = bindingOverridesForJob(name, job);
  let merged = mergeBinding(base, override, name);
  const registryCode = contract.feature_binding_map?.[name];
  if (registryCode) {
    const entry = contract.binding_registry?.[registryCode] || {};
    const overlaySet = entry.overlay_rules_set;
    if (overlaySet) {
      const overlay = resolveRulesSet(overlaySet).binding_overrides?.[name] || {};
      merged = mergeBinding(merged, overlay, name);
    }
  }
  const overlayField =
    contract.job_overlay?.envelope_field || "overlay_rules_set";
  const jobOverlaySet = job[overlayField];
  if (jobOverlaySet) {
    const jobOverlay =
      resolveRulesSet(jobOverlaySet).binding_overrides?.[name] || {};
    merged = mergeBinding(merged, jobOverlay, name);
  }
  return merged;
}

function capFeature(value) {
  const cap = contract.feature_normalize_cap;
  if (cap == null) return value;
  return Math.min(value, cap);
}

function pickContainer(doc) {
  const selector = contract.model_container_selector;
  const podLabels = doc?.spec?.template?.metadata?.labels || {};
  const containers = doc?.spec?.template?.spec?.containers || [];
  if (podLabels[selector.label_key] === selector.label_value) {
    const byName = containers.find((c) =>
      c.name?.includes(selector.fallback_name_contains),
    );
    if (byName) return byName;
  }
  const byName = containers.find((c) =>
    c.name?.includes(selector.fallback_name_contains),
  );
  return byName || containers[0] || {};
}

function parseRollingUnavailable(raw, replicas, binding) {
  if (raw == null) return 0;
  const spec = binding.rolling_unavailable_parse || {};
  const text = String(raw);
  const suffix = spec.percent_suffix || "%";
  if (text.endsWith(suffix)) {
    const pct = Number.parseInt(text.slice(0, -suffix.length), 10);
    const scaled = (replicas * pct) / 100;
    if (spec.percent_mode === "ceil_of_replicas") {
      return Math.ceil(scaled);
    }
    return Math.floor(scaled);
  }
  return Number.parseInt(text, 10);
}

function effectiveReplicas(doc, binding) {
  const replicas = doc?.spec?.replicas ?? 0;
  if (!binding.adjust_rolling) return replicas;
  const rolling = doc?.spec?.strategy?.rollingUpdate?.maxUnavailable;
  if (rolling == null) return replicas;
  const unavailable = parseRollingUnavailable(rolling, replicas, binding);
  return Math.max(0, replicas - unavailable);
}

function extractFeatures(doc, job) {
  const container = pickContainer(doc);
  const podMeta = doc?.spec?.template?.metadata || {};
  const framework = podMeta.annotations?.["serving.mlp.io/framework"] || "";
  const replicaBinding = bindingSpec("replicas_meets_min", job);
  const replicas = effectiveReplicas(doc, replicaBinding);

  const byName = Object.fromEntries(
    contract.feature_order.map((name) => {
      const spec = bindingSpec(name, job);
      switch (name) {
        case "cpu_request_norm":
          return [
            name,
            capFeature(
              parseCpuMillicores(container.resources?.requests?.cpu) / spec.divisor,
            ),
          ];
        case "memory_request_norm":
          return [
            name,
            capFeature(
              parseMemoryMib(container.resources?.requests?.memory) / spec.divisor,
            ),
          ];
        case "gpu_limit_present":
          return [
            name,
            Number(container.resources?.limits?.["nvidia.com/gpu"] || 0) > 0 ? 1 : 0,
          ];
        case "readiness_probe_present":
          return [name, container.readinessProbe ? 1 : 0];
        case "liveness_probe_present":
          return [name, container.livenessProbe ? 1 : 0];
        case "model_checksum_annotated":
          return [
            name,
            podMeta.annotations?.["model.mlp.io/artifact-sha256"] ? 1 : 0,
          ];
        case "serving_framework_allowed":
          return [
            name,
            rules.serving_frameworks_allowed.includes(framework) ? 1 : 0,
          ];
        case "replicas_meets_min":
          return [name, replicas >= spec.minimum ? 1 : 0];
        default:
          return [name, 0];
      }
    }),
  );

  return contract.feature_order.map((name) => byName[name]);
}

function scoreFeatures(featureVector) {
  const kernel = tf.tensor2d(weights.kernel);
  const bias = tf.tensor1d(weights.bias);
  const input = tf.tensor2d([featureVector]);
  const logits = input.matMul(kernel).add(bias);
  const score = tf.sigmoid(logits).dataSync()[0];
  kernel.dispose();
  bias.dispose();
  input.dispose();
  logits.dispose();
  return bankersRound(score, contract.score_rounding.decimals);
}

async function mlflowFetch(route, body) {
  const res = await fetch(`${TRACKING_URI}/api/2.0/mlflow${route}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`MLflow ${route} failed: ${res.status} ${text}`);
  }
  return res.json();
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureExperiment() {
  const name = manifest.experiment_name;
  let lastError;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      const existing = await fetch(
        `${TRACKING_URI}/api/2.0/mlflow/experiments/get-by-name?experiment_name=${encodeURIComponent(name)}`,
      );
      if (existing.ok) {
        const data = await existing.json();
        return data.experiment.experiment_id;
      }

      try {
        const created = await mlflowFetch("/experiments/create", { name });
        return created.experiment_id;
      } catch (createErr) {
        const message = String(createErr.message || createErr);
        if (
          message.includes("RESOURCE_ALREADY_EXISTS")
          || message.includes("409")
          || message.includes("already exists")
        ) {
          continue;
        }
        throw createErr;
      }
    } catch (err) {
      lastError = err;
      await sleep(500 + attempt * 250);
    }
  }
  throw lastError;
}

function writeArtifact(experimentId, runId, payload) {
  const artifactDir = path.join(ARTIFACT_ROOT, experimentId, runId, "artifacts");
  fs.mkdirSync(artifactDir, { recursive: true });
  fs.writeFileSync(
    path.join(artifactDir, manifest.artifact_name),
    JSON.stringify(payload, null, 2),
  );
}

function verdictTag(internalVerdict) {
  return rules.verdict_lexicon?.[internalVerdict] || internalVerdict;
}

async function logRun(experimentId, job, score, verdict, featureVector, profile) {
  const run = await mlflowFetch("/runs/create", { experiment_id: experimentId });
  const runId = run.run.info.run_id;

  const params = {
    job_id: job.job_id,
    spec_path: job.spec_path,
    profile_ref: profile.profileRef,
    resolved_profile: profile.resolved,
  };
  for (const key of manifest.param_keys) {
    await mlflowFetch("/runs/log-parameter", {
      run_id: runId,
      key,
      value: String(params[key] ?? ""),
    });
  }

  await mlflowFetch("/runs/log-metric", {
    run_id: runId,
    key: manifest.metric_key,
    value: score,
    timestamp: manifest.metric_timestamp_ms,
  });

  const tags = {
    verdict: verdictTag(verdict),
    queue_priority: String(job.priority),
  };
  for (const key of manifest.tag_keys) {
    await mlflowFetch("/runs/set-tag", {
      run_id: runId,
      key,
      value: String(tags[key] ?? ""),
    });
  }

  writeArtifact(experimentId, runId, {
    job_id: job.job_id,
    readiness: score,
    verdict: verdictTag(verdict),
    profile_ref: profile.profileRef,
    resolved_profile: profile.resolved,
    feature_vector: featureVector,
  });

  return runId;
}

function loadJobs() {
  const files = fs.readdirSync(PENDING).filter((f) => f.endsWith(".json"));
  const jobs = files.map((file) => ({
    file,
    envelope: JSON.parse(fs.readFileSync(path.join(PENDING, file), "utf8")),
  }));
  jobs.sort((a, b) => {
    if (b.envelope.priority !== a.envelope.priority) {
      return b.envelope.priority - a.envelope.priority;
    }
    return a.envelope.job_id.localeCompare(b.envelope.job_id);
  });
  return jobs;
}

async function main() {
  fs.mkdirSync(path.join(ROOT, "output"), { recursive: true });
  fs.mkdirSync(DONE, { recursive: true });

  const experimentId = await ensureExperiment();
  const results = [];
  let skipped = 0;

  for (const { file, envelope: job } of loadJobs()) {
    const profile = resolveProfile(job.profile_ref);

    if (job.defer) {
      fs.renameSync(path.join(PENDING, file), path.join(DONE, file));
      skipped += 1;
      results.push({
        job_id: job.job_id,
        priority: job.priority,
        spec_path: job.spec_path,
        profile_ref: profile.profileRef,
        resolved_profile: profile.resolved,
        readiness: null,
        verdict: "deferred",
        deferred: true,
      });
      continue;
    }

    const doc = yaml.load(fs.readFileSync(job.spec_path, "utf8"));
    const features = extractFeatures(doc, job);
    const score = scoreFeatures(features);
    const threshold = rules.profiles[profile.resolved]?.min_score ?? 1;
    const verdict = score >= threshold ? "ready" : "not_ready";

    await logRun(experimentId, job, score, verdict, features, profile);
    fs.renameSync(path.join(PENDING, file), path.join(DONE, file));

    results.push({
      job_id: job.job_id,
      priority: job.priority,
      spec_path: job.spec_path,
      profile_ref: profile.profileRef,
      resolved_profile: profile.resolved,
      readiness: score,
      verdict,
      deferred: false,
    });
  }

  const report = {
    experiment: manifest.experiment_name,
    jobs: results,
    summary: {
      processed: results.filter((r) => !r.deferred).length,
      ready: results.filter((r) => r.verdict === "ready").length,
      not_ready: results.filter((r) => r.verdict === "not_ready").length,
      skipped,
    },
  };

  const serialized = JSON.stringify(report, null, 2);
  fs.writeFileSync(OUTPUT, serialized);
  console.log(serialized);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
