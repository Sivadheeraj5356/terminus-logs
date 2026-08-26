from __future__ import annotations

import json
import math
import os
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

import yaml

ROOT = Path("/app")
TRUSTED_PENDING = Path("/tests/data/pending")


def _config_path(env_key: str, default: str) -> Path:
    return Path(os.environ.get(env_key, default))


def load_contract() -> dict:
    contract = json.loads(
        _config_path(
            "READINESS_CONTRACT_PATH",
            "/app/config/readiness_contract.json",
        ).read_text()
    )
    defaults = contract.get("config_paths", {}).get("defaults", {})
    env_contract = contract.get("config_paths", {}).get(
        "contract_env", "READINESS_CONTRACT_PATH"
    )
    path = Path(
        os.environ.get(
            env_contract, defaults.get("contract", "/app/config/readiness_contract.json")
        )
    )
    return json.loads(path.read_text())


def load_rules() -> dict:
    contract = json.loads(
        Path(
            os.environ.get(
                "READINESS_CONTRACT_PATH",
                "/app/config/readiness_contract.json",
            )
        ).read_text()
    )
    defaults = contract.get("config_paths", {}).get("defaults", {})
    env_rules = contract.get("config_paths", {}).get("rules_env", "READINESS_RULES_PATH")
    path = Path(
        os.environ.get(env_rules, defaults.get("rules", "/app/config/readiness_rules.json"))
    )
    return json.loads(path.read_text())


def load_manifest() -> dict:
    contract = load_contract()
    defaults = contract.get("config_paths", {}).get("defaults", {})
    env_manifest = contract.get("config_paths", {}).get(
        "manifest_env", "MLFLOW_MANIFEST_PATH"
    )
    path = Path(
        os.environ.get(
            env_manifest, defaults.get("manifest", "/app/config/mlflow_manifest.json")
        )
    )
    return json.loads(path.read_text())


def load_weights() -> dict:
    contract = load_contract()
    defaults = contract.get("config_paths", {}).get("defaults", {})
    env_weights = contract.get("config_paths", {}).get("weights_env", "MODEL_WEIGHTS_PATH")
    path = Path(
        os.environ.get(env_weights, defaults.get("weights", "/app/model/weights.json"))
    )
    return json.loads(path.read_text())


def bankers_round(value: float, decimals: int) -> float:
    quant = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_EVEN))


def parse_cpu_millicores(value) -> float:
    if value is None:
        return 0.0
    raw = str(value)
    if raw.endswith("m"):
        return float(raw[:-1])
    return float(raw) * 1000


def parse_memory_mib(value) -> float:
    if value is None:
        return 0.0
    raw = str(value)
    if raw.endswith("Mi"):
        return float(raw[:-2])
    if raw.endswith("Gi"):
        return float(raw[:-2]) * 1024
    return float(raw) / (1024 * 1024)


def resolve_profile(profile_ref: str, rules: dict) -> tuple[str, str]:
    resolved = profile_ref
    seen: set[str] = set()
    while resolved in rules.get("profile_aliases", {}) and resolved not in seen:
        seen.add(resolved)
        resolved = rules["profile_aliases"][resolved]
    return profile_ref, resolved


def resolve_rules_set(ref: str, rules: dict, seen: set[str] | None = None) -> dict:
    if seen is None:
        seen = set()
    if ref in seen:
        return {"binding_overrides": {}}
    seen.add(ref)
    rules_set = rules.get("rules_sets", {}).get(ref)
    if rules_set is None:
        rules_set = rules["rules_sets"]["default"]
    overrides = dict(rules_set.get("binding_overrides", {}))
    parent_ref = rules_set.get("extends")
    if parent_ref:
        parent = resolve_rules_set(parent_ref, rules, seen)
        overrides = {**parent["binding_overrides"], **overrides}
    return {"binding_overrides": overrides}


def merge_binding(
    base: dict, override: dict, policy: str, feature_name: str | None = None, contract: dict | None = None
) -> dict:
    if contract and feature_name:
        per_feature = contract.get("binding_merge", {}).get("per_feature", {})
        policy = per_feature.get(feature_name, policy)
    if policy == "registry_wins":
        return {**override, **base}
    return {**base, **override}


def merge_stack_overrides(name: str, stack: list[str], rules: dict, contract: dict) -> dict:
    policy = contract.get("rules_stack_merge", {}).get("override_policy", "last_wins")
    merged: dict = {}
    for ref in stack:
        chunk = dict(resolve_rules_set(ref, rules)["binding_overrides"].get(name, {}))
        if policy == "first_wins":
            for key, value in chunk.items():
                if key not in merged:
                    merged[key] = value
        else:
            merged = {**merged, **chunk}
    return merged


def binding_overrides_for_job(name: str, job: dict, contract: dict, rules: dict) -> dict:
    selection = contract.get("rules_selection", {})
    precedence = selection.get("precedence", "ref_default")
    stack = job.get("rules_profile_stack")
    if stack and precedence == "stack_over_ref":
        return merge_stack_overrides(name, stack, rules, contract)
    if stack:
        return merge_stack_overrides(name, stack, rules, contract)
    rules_ref = job.get("rules_ref", "default")
    rules_set = resolve_rules_set(rules_ref, rules)
    return dict(rules_set["binding_overrides"].get(name, {}))


def binding_spec(name: str, job: dict, contract: dict, rules: dict) -> dict:
    base = dict(contract["bindings"][name])
    override = binding_overrides_for_job(name, job, contract, rules)
    policy = contract.get("binding_merge", {}).get("policy", "rules_wins")
    merged = merge_binding(base, override, policy, name, contract)
    registry_code = contract.get("feature_binding_map", {}).get(name)
    if registry_code:
        entry = contract.get("binding_registry", {}).get(registry_code, {})
        overlay_set = entry.get("overlay_rules_set")
        if overlay_set:
            overlay = resolve_rules_set(overlay_set, rules)["binding_overrides"].get(name, {})
            merged = merge_binding(merged, overlay, policy, name, contract)
    overlay_field = contract.get("job_overlay", {}).get("envelope_field", "overlay_rules_set")
    job_overlay_set = job.get(overlay_field)
    if job_overlay_set:
        job_overlay = resolve_rules_set(job_overlay_set, rules)["binding_overrides"].get(name, {})
        merged = merge_binding(merged, job_overlay, policy, name, contract)
    return merged


def cap_feature(value: float, contract: dict) -> float:
    cap = contract.get("feature_normalize_cap")
    if cap is None:
        return value
    return min(value, cap)


def pick_container(doc: dict, contract: dict) -> dict:
    selector = contract["model_container_selector"]
    pod_labels = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
    containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    if pod_labels.get(selector["label_key"]) == selector["label_value"]:
        for container in containers:
            if selector["fallback_name_contains"] in (container.get("name") or ""):
                return container
    for container in containers:
        if selector["fallback_name_contains"] in (container.get("name") or ""):
            return container
    return containers[0] if containers else {}


def parse_rolling_unavailable(raw, replicas: int, binding: dict) -> int:
    if raw is None:
        return 0
    spec = binding.get("rolling_unavailable_parse", {})
    text = str(raw)
    suffix = spec.get("percent_suffix", "%")
    if text.endswith(suffix):
        pct = int(text[: -len(suffix)])
        mode = spec.get("percent_mode", "floor_of_replicas")
        scaled = replicas * pct / 100
        if mode == "ceil_of_replicas":
            return math.ceil(scaled)
        return math.floor(scaled)
    return int(text)


def effective_replicas(doc: dict, binding: dict) -> int:
    replicas = doc.get("spec", {}).get("replicas", 0) or 0
    if not binding.get("adjust_rolling"):
        return replicas
    rolling = (
        doc.get("spec", {}).get("strategy", {}).get("rollingUpdate", {}).get("maxUnavailable")
    )
    if rolling is None:
        return replicas
    unavailable = parse_rolling_unavailable(rolling, replicas, binding)
    return max(0, replicas - unavailable)


def extract_features(doc: dict, job: dict, contract: dict, rules: dict) -> list[float]:
    container = pick_container(doc, contract)
    pod_meta = doc.get("spec", {}).get("template", {}).get("metadata", {})
    framework = pod_meta.get("annotations", {}).get("serving.mlp.io/framework", "")
    replica_binding = binding_spec("replicas_meets_min", job, contract, rules)
    replicas = effective_replicas(doc, replica_binding)

    values: dict[str, float] = {}
    for name in contract["feature_order"]:
        spec = binding_spec(name, job, contract, rules)
        if name == "cpu_request_norm":
            values[name] = parse_cpu_millicores(
                container.get("resources", {}).get("requests", {}).get("cpu")
            ) / spec["divisor"]
        elif name == "memory_request_norm":
            values[name] = parse_memory_mib(
                container.get("resources", {}).get("requests", {}).get("memory")
            ) / spec["divisor"]
        elif name == "gpu_limit_present":
            values[name] = (
                1.0
                if float(
                    container.get("resources", {}).get("limits", {}).get("nvidia.com/gpu", 0)
                    or 0
                )
                > 0
                else 0.0
            )
        elif name == "readiness_probe_present":
            values[name] = 1.0 if container.get("readinessProbe") else 0.0
        elif name == "liveness_probe_present":
            values[name] = 1.0 if container.get("livenessProbe") else 0.0
        elif name == "model_checksum_annotated":
            values[name] = (
                1.0
                if pod_meta.get("annotations", {}).get("model.mlp.io/artifact-sha256")
                else 0.0
            )
        elif name == "serving_framework_allowed":
            values[name] = 1.0 if framework in rules["serving_frameworks_allowed"] else 0.0
        elif name == "replicas_meets_min":
            values[name] = 1.0 if replicas >= spec["minimum"] else 0.0
        else:
            values[name] = 0.0
        if name in ("cpu_request_norm", "memory_request_norm"):
            values[name] = cap_feature(values[name], contract)
    return [values[name] for name in contract["feature_order"]]


def score_features(feature_vector: list[float], contract: dict, weights: dict) -> float:
    kernel = weights["kernel"]
    bias = weights["bias"][0]
    total = bias
    for idx, feature in enumerate(feature_vector):
        total += feature * kernel[idx][0]
    score = 1 / (1 + math.exp(-total))
    return bankers_round(score, contract["score_rounding"]["decimals"])


def verdict_tag(internal_verdict: str, rules: dict) -> str:
    return rules.get("verdict_lexicon", {}).get(internal_verdict, internal_verdict)


def load_trusted_envelopes() -> list[dict]:
    jobs = []
    for path in sorted(TRUSTED_PENDING.glob("*.json"), key=lambda p: p.name):
        jobs.append(json.loads(path.read_text()))
    jobs.sort(key=lambda j: (-j["priority"], j["job_id"]))
    return jobs


def expected_report_from_done_queue() -> dict:
    contract = load_contract()
    rules = load_rules()
    manifest = load_manifest()
    weights = load_weights()

    jobs = load_trusted_envelopes()

    results = []
    ready = 0
    not_ready = 0
    skipped = 0

    for job in jobs:
        profile_ref, resolved = resolve_profile(job["profile_ref"], rules)
        if job.get("defer"):
            skipped += 1
            results.append(
                {
                    "job_id": job["job_id"],
                    "priority": job["priority"],
                    "spec_path": job["spec_path"],
                    "profile_ref": profile_ref,
                    "resolved_profile": resolved,
                    "readiness": None,
                    "verdict": "deferred",
                    "deferred": True,
                }
            )
            continue

        doc = yaml.safe_load(Path(job["spec_path"]).read_text())
        features = extract_features(doc, job, contract, rules)
        score = score_features(features, contract, weights)
        threshold = rules["profiles"][resolved]["min_score"]
        verdict = "ready" if score >= threshold else "not_ready"
        if verdict == "ready":
            ready += 1
        else:
            not_ready += 1
        results.append(
            {
                "job_id": job["job_id"],
                "priority": job["priority"],
                "spec_path": job["spec_path"],
                "profile_ref": profile_ref,
                "resolved_profile": resolved,
                "readiness": score,
                "verdict": verdict,
                "deferred": False,
            }
        )

    return {
        "experiment": manifest["experiment_name"],
        "jobs": results,
        "summary": {
            "processed": ready + not_ready,
            "ready": ready,
            "not_ready": not_ready,
            "skipped": skipped,
        },
    }


def expected_mlflow_run(job_id: str) -> dict | None:
    contract = load_contract()
    rules = load_rules()
    manifest = load_manifest()
    weights = load_weights()

    job = None
    for path in TRUSTED_PENDING.glob("*.json"):
        envelope = json.loads(path.read_text())
        if envelope["job_id"] == job_id:
            job = envelope
            break
    if job is None or job.get("defer"):
        return None

    profile_ref, resolved = resolve_profile(job["profile_ref"], rules)
    doc = yaml.safe_load(Path(job["spec_path"]).read_text())
    features = extract_features(doc, job, contract, rules)
    score = score_features(features, contract, weights)
    threshold = rules["profiles"][resolved]["min_score"]
    verdict = "ready" if score >= threshold else "not_ready"

    return {
        "job_id": job_id,
        "priority": job["priority"],
        "params": {
            "job_id": job_id,
            "spec_path": job["spec_path"],
            "profile_ref": profile_ref,
            "resolved_profile": resolved,
        },
        "metric_key": manifest["metric_key"],
        "metric_value": score,
        "metric_timestamp_ms": manifest["metric_timestamp_ms"],
        "verdict": verdict_tag(verdict, rules),
        "artifact_name": manifest["artifact_name"],
        "artifact": {
            "job_id": job_id,
            "readiness": score,
            "verdict": verdict_tag(verdict, rules),
            "profile_ref": profile_ref,
            "resolved_profile": resolved,
            "feature_vector": features,
        },
    }
