import copy
import hashlib
import json
import os
import shutil
import subprocess
from itertools import combinations
from pathlib import Path


APP_DIR = Path(os.environ.get("APP_DIR", "/app/task_file"))
SCRIPT = APP_DIR / "adjudicate.js"
PUBLIC_INPUT = APP_DIR / "input_data"

PUBLIC_HASHES = {
    "candidates.json": "3104975561c11da8cd801c6af6a32a787f994a6e916e3e518b5dc8c92c40b80d",
    "exceptions.json": "79b604f7f621164be13423bd04ed2ed5a3fc1240a2d1422b74151e2d6789c158",
    "policy.json": "2339f209244a3a83893f02f51c4a9132f2d6d6711e06b29a2ceb57785d90f26f",
    "runtime_state.json": "8408bb23e17d5cbac4fbd1a1b3375a5a7852a6dbb8afa592c83551ae5ae4a2fc",
    "test_runs.json": "325e8e706ad58446166ff1c38a30a52f3ac773e3016fb007cad4dc7df788f977",
}


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bundle(input_dir):
    return {
        "policy": read_json(input_dir / "policy.json"),
        "runtime": read_json(input_dir / "runtime_state.json"),
        "tests": read_json(input_dir / "test_runs.json"),
        "exceptions": read_json(input_dir / "exceptions.json"),
        "candidates": read_json(input_dir / "candidates.json"),
    }


def iso_key(value):
    return value


def iso_hours(current, built):
    from datetime import datetime, timezone

    def parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    return (parse(current) - parse(built)).total_seconds() / 3600.0


def is_not_expired(current, expires):
    from datetime import datetime, timezone

    now = datetime.fromisoformat(current.replace("Z", "+00:00")).astimezone(timezone.utc)
    end = datetime.fromisoformat(expires.replace("Z", "+00:00")).astimezone(timezone.utc)
    return end >= now


def semver(value):
    parts = [int(part) for part in value.split(".")]
    assert len(parts) == 3
    return tuple(parts)


def version_at_least(actual, minimum):
    return semver(actual) >= semver(minimum)


def version_newer(candidate, active):
    if active is None:
        return True
    return semver(candidate) > semver(active["version"])


def version_bonus(candidate, active):
    if active is None:
        return 60
    cand = semver(candidate)
    old = semver(active["version"])
    raw = max(0, cand[0] - old[0]) * 40 + max(0, cand[1] - old[1]) * 8 + max(0, cand[2] - old[2]) * 2
    return min(raw, 60)


def maps(bundle):
    runtime = {
        (row["service"], row["env"]): row
        for row in bundle["runtime"].get("active", [])
    }
    runs = {row["id"]: row for row in bundle["tests"].get("runs", [])}
    windows = {row["id"]: row for row in bundle["policy"].get("windows", [])}
    exceptions = bundle["exceptions"].get("exceptions", [])
    return runtime, runs, windows, exceptions


NONWAIVABLE = {
    "critical_vuln",
    "untrusted_signer",
    "weak_slsa",
    "attestation_mismatch",
    "unknown_service",
    "unknown_env",
}


def valid_exception(candidate, reason, bundle):
    current = bundle["policy"]["current_time"]
    for exc in bundle["exceptions"].get("exceptions", []):
        if exc["token"] not in candidate.get("exception_tokens", []):
            continue
        if exc["service"] != candidate["service"] or exc["env"] != candidate["env"]:
            continue
        if exc["reason"] != reason:
            continue
        if is_not_expired(current, exc["expires_at"]):
            return True
    return False


def evaluate_candidate(candidate, bundle):
    policy = bundle["policy"]
    runtime, runs, windows, _ = maps(bundle)
    services = policy["services"]
    envs = policy["envs"]
    reasons = set()
    waived = set()

    service_policy = services.get(candidate["service"])
    if service_policy is None:
        reasons.add("unknown_service")
    if candidate["env"] not in envs:
        reasons.add("unknown_env")

    active = runtime.get((candidate["service"], candidate["env"]))
    if active is not None:
        if not version_newer(candidate["version"], active):
            reasons.add("not_newer_version")
        if candidate["digest"] == active["digest"]:
            reasons.add("already_active_digest")

    if service_policy is not None:
        if iso_hours(policy["current_time"], candidate["built_at"]) > service_policy["max_age_hours"]:
            reasons.add("stale_build")
        signer_state = policy["trusted_signers"].get(candidate["signer"], {})
        if not signer_state.get("active", False) or candidate["signer"] not in service_policy["allowed_signers"]:
            reasons.add("untrusted_signer")
        if candidate["attestations"].get("slsa_level", 0) < service_policy["min_slsa"]:
            reasons.add("weak_slsa")
        run = runs.get(candidate["attestations"].get("test_run_id"))
        if (
            run is None
            or run.get("status") != "passed"
            or run.get("digest") != candidate["digest"]
            or run.get("source_ref") != candidate["attestations"].get("source_ref")
            or run.get("coverage", -1) < service_policy["min_coverage"]
            or run.get("flaky") is not False
        ):
            reasons.add("attestation_mismatch")
        if any(row["severity"] == "critical" for row in candidate.get("sbom", [])):
            reasons.add("critical_vuln")
        if any(row.get("license") in service_policy["forbidden_licenses"] for row in candidate.get("sbom", [])):
            reasons.add("forbidden_license")
        for flag in service_policy.get("exception_required_for", []):
            if candidate.get("features", {}).get(flag) is True:
                reasons.add("missing_required_exception")

    window = windows.get(candidate["requested_window"])
    if window is None or window.get("env") != candidate["env"] or iso_key(window.get("starts_at", "")) <= iso_key(policy["current_time"]):
        reasons.add("outside_window")

    for reason in list(reasons):
        if reason not in NONWAIVABLE and valid_exception(candidate, reason, bundle):
            reasons.remove(reason)
            waived.add(reason)

    ordered_reasons = [reason for reason in policy["reason_order"] if reason in reasons]
    ordered_waived = [reason for reason in policy["reason_order"] if reason in waived]
    if ordered_reasons:
        return {"eligible": False, "reasons": ordered_reasons, "warnings": ordered_waived}

    vuln_weights = policy["risk_weights"]["vulnerabilities"]
    feature_weights = policy["risk_weights"]["features"]
    waiver_weights = policy["risk_weights"]["waivers"]
    risk = 0
    for row in candidate.get("sbom", []):
        if row["severity"] != "critical":
            risk += vuln_weights.get(row["severity"], 0)
    for name, weight in feature_weights.items():
        if candidate.get("features", {}).get(name) is True:
            risk += weight
    for reason in ordered_waived:
        risk += waiver_weights.get(reason, 0)

    value = service_policy["priority"] + candidate["rollout_impact"] + version_bonus(candidate["version"], active)
    return {
        "eligible": True,
        "risk_score": risk,
        "deployment_value": value,
        "warnings": [f"waived:{reason}" for reason in ordered_waived],
    }


def valid_plan(selected, evaluations, bundle):
    policy = bundle["policy"]
    windows = {row["id"]: row for row in policy["windows"]}
    seen_service_env = set()
    selected_by_service_env = {}
    env_counts = {}
    window_counts = {}
    window_risk = {}
    window_db = {}

    for candidate in selected:
        key = (candidate["service"], candidate["env"])
        if key in seen_service_env:
            return False
        seen_service_env.add(key)
        selected_by_service_env[key] = candidate
        env_counts[candidate["env"]] = env_counts.get(candidate["env"], 0) + 1
        window_id = candidate["requested_window"]
        window_counts[window_id] = window_counts.get(window_id, 0) + 1
        window_risk[window_id] = window_risk.get(window_id, 0) + evaluations[candidate["id"]]["risk_score"]
        if candidate.get("features", {}).get("db_migration") is True:
            window_db[window_id] = window_db.get(window_id, 0) + 1

    for candidate in selected:
        candidate_start = windows[candidate["requested_window"]]["starts_at"]
        visible_runtime = {
            (row["service"], row["env"]): row["version"]
            for row in bundle["runtime"].get("active", [])
        }
        for deployed in selected:
            deployed_start = windows[deployed["requested_window"]]["starts_at"]
            if deployed_start <= candidate_start:
                visible_runtime[(deployed["service"], deployed["env"])] = deployed["version"]
        for requirement in candidate.get("requires", []):
            key = (requirement["service"], requirement.get("env", candidate["env"]))
            version = visible_runtime.get(key)
            if version is None or not version_at_least(version, requirement["min_version"]):
                return False
        for conflict in candidate.get("conflicts_with", []):
            key = (conflict["service"], conflict.get("env", candidate["env"]))
            if key in selected_by_service_env:
                return False

    for env, count in env_counts.items():
        if count > policy["envs"][env]["max_approvals"]:
            return False
    for window_id, count in window_counts.items():
        window = windows[window_id]
        if count > window["capacity"]:
            return False
        if window_risk[window_id] > window["risk_budget"]:
            return False
        if window_db.get(window_id, 0) > window["max_db_migrations"]:
            return False
    return True


def choose_plan(candidates, evaluations, bundle):
    eligible = [candidate for candidate in candidates if evaluations[candidate["id"]]["eligible"]]
    best = None
    for size in range(len(eligible) + 1):
        for combo in combinations(eligible, size):
            if not valid_plan(combo, evaluations, bundle):
                continue
            value = sum(evaluations[row["id"]]["deployment_value"] for row in combo)
            risk = sum(evaluations[row["id"]]["risk_score"] for row in combo)
            ids = ",".join(sorted(row["id"] for row in combo))
            key = (value, -risk, len(combo), tuple(chr(255 - ord(ch)) for ch in ids))
            if best is None or key > best[0]:
                best = (key, list(combo))
    assert best is not None
    return best[1]


def expected_output(bundle):
    candidates = bundle["candidates"]["candidates"]
    evaluations = {candidate["id"]: evaluate_candidate(candidate, bundle) for candidate in candidates}
    selected_candidates = choose_plan(candidates, evaluations, bundle)
    selected_ids = {candidate["id"] for candidate in selected_candidates}
    selected_service_env = {(candidate["service"], candidate["env"]) for candidate in selected_candidates}
    windows = {row["id"]: row for row in bundle["policy"]["windows"]}

    selected = []
    rejected = []
    deferred = []
    for candidate in candidates:
        ev = evaluations[candidate["id"]]
        if not ev["eligible"]:
            rejected.append({"candidate_id": candidate["id"], "reasons": ev["reasons"]})
        elif candidate["id"] in selected_ids:
            selected.append(
                {
                    "candidate_id": candidate["id"],
                    "service": candidate["service"],
                    "env": candidate["env"],
                    "window_id": candidate["requested_window"],
                    "deployment_value": ev["deployment_value"],
                    "risk_score": ev["risk_score"],
                    "warnings": ev["warnings"],
                }
            )
        else:
            reason = (
                "lower_ranked_candidate"
                if (candidate["service"], candidate["env"]) in selected_service_env
                else "capacity_or_budget"
            )
            deferred.append({"candidate_id": candidate["id"], "reasons": [reason]})

    selected.sort(key=lambda row: (row["env"], windows[row["window_id"]]["starts_at"], row["service"], row["candidate_id"]))
    rejected.sort(key=lambda row: row["candidate_id"])
    deferred.sort(key=lambda row: row["candidate_id"])
    by_env = {}
    by_window = {}
    for row in selected:
        by_env[row["env"]] = by_env.get(row["env"], 0) + 1
        by_window[row["window_id"]] = by_window.get(row["window_id"], 0) + 1
    return {
        "selected": selected,
        "deferred": deferred,
        "rejected": rejected,
        "summary": {
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "rejected_count": len(rejected),
            "total_value": sum(row["deployment_value"] for row in selected),
            "total_risk": sum(row["risk_score"] for row in selected),
            "by_env": dict(sorted(by_env.items())),
            "by_window": dict(sorted(by_window.items())),
        },
    }


def run_agent(input_dir, tmp_path):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", str(SCRIPT), str(input_dir), str(out_dir)],
        cwd=APP_DIR,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    output_file = out_dir / "deployment_decisions.json"
    assert output_file.exists(), "deployment_decisions.json was not written"
    return read_json(output_file)


def assert_schema_and_partition(actual, bundle):
    assert set(actual) == {"selected", "deferred", "rejected", "summary"}
    assert isinstance(actual["selected"], list)
    assert isinstance(actual["deferred"], list)
    assert isinstance(actual["rejected"], list)
    assert isinstance(actual["summary"], dict)

    all_ids = [row["id"] for row in bundle["candidates"]["candidates"]]
    seen = []
    for row in actual["selected"]:
        assert set(row) == {"candidate_id", "service", "env", "window_id", "deployment_value", "risk_score", "warnings"}
        assert isinstance(row["deployment_value"], int)
        assert isinstance(row["risk_score"], int)
        assert isinstance(row["warnings"], list)
        seen.append(row["candidate_id"])
    for group in ("deferred", "rejected"):
        for row in actual[group]:
            assert set(row) == {"candidate_id", "reasons"}
            assert isinstance(row["reasons"], list)
            seen.append(row["candidate_id"])
    assert sorted(seen) == sorted(all_ids)
    assert len(seen) == len(set(seen))


def public_actual_expected(tmp_path):
    bundle = load_bundle(PUBLIC_INPUT)
    return bundle, run_agent(PUBLIC_INPUT, tmp_path), expected_output(bundle)


def generated_actual_expected(tmp_path):
    cases = []
    for seed in range(12):
        case_dir = tmp_path / f"case-{seed}"
        bundle = variant_bundle(seed)
        write_bundle(bundle, case_dir)
        actual = run_agent(case_dir, tmp_path / f"run-{seed}")
        cases.append((bundle, actual, expected_output(bundle)))
    return cases


def copy_public_input(tmp_path):
    target = tmp_path / "input"
    shutil.copytree(PUBLIC_INPUT, target)
    return target


def variant_bundle(seed):
    bundle = copy.deepcopy(load_bundle(PUBLIC_INPUT))
    policy = bundle["policy"]
    candidates = bundle["candidates"]["candidates"]
    runs = bundle["tests"]["runs"]

    policy["windows"][0]["risk_budget"] = 112 + (seed % 4) * 10
    policy["windows"][1]["capacity"] = 1 + (seed % 2)
    policy["envs"]["prod"]["max_approvals"] = 2 + (seed % 2)

    if seed % 3 == 0:
        for exc in bundle["exceptions"]["exceptions"]:
            if exc["token"] == "EX-CAT-LIC-07":
                exc["expires_at"] = "2026-07-04T09:00:00Z"

    if seed % 4 == 1:
        candidates[0]["requested_window"] = "prod-late"
        candidates[0]["rollout_impact"] += 4

    alt_id = f"id-41{seed}"
    alt_digest = f"sha256:id-41{seed}"
    candidates.append(
        {
            "id": alt_id,
            "service": "identity",
            "env": "prod",
            "version": f"4.1.{seed}",
            "digest": alt_digest,
            "base_image": "distroless@sha256:base-id-b",
            "built_at": "2026-07-03T17:00:00Z",
            "signer": "sigstore-root",
            "requested_window": "prod-late" if seed % 2 else "prod-early",
            "attestations": {"slsa_level": 4, "source_ref": f"refs/tags/identity-v4.1.{seed}", "test_run_id": f"tr-{alt_id}"},
            "features": {"privileged": False, "db_migration": seed % 5 == 0, "public_api": True},
            "sbom": [
                {"package": "jwt-core", "severity": "medium", "license": "BSD-3-Clause"},
                {"package": "oauth-cache", "severity": "low", "license": "MIT"},
            ],
            "exception_tokens": [],
            "rollout_impact": 18 + seed,
        }
    )
    runs.append(
        {
            "id": f"tr-{alt_id}",
            "status": "passed",
            "digest": alt_digest,
            "source_ref": f"refs/tags/identity-v4.1.{seed}",
            "coverage": 94,
            "flaky": False,
        }
    )

    if seed % 2 == 1:
        candidates.reverse()

    pay_stage_id = f"pay-stage-{seed}"
    pay_stage_digest = f"sha256:{pay_stage_id}"
    cat_stage_id = f"cat-stage-{seed}"
    cat_stage_digest = f"sha256:{cat_stage_id}"
    sea_stage_id = f"sea-stage-{seed}"
    sea_stage_digest = f"sha256:{sea_stage_id}"
    candidates.extend(
        [
            {
                "id": pay_stage_id,
                "service": "payments",
                "env": "stage",
                "version": f"2.5.{seed}",
                "digest": pay_stage_digest,
                "base_image": "ubuntu:22.04@sha256:base-pay-stage",
                "built_at": "2026-07-03T20:00:00Z",
                "signer": "payments-ca",
                "requested_window": "stage-afternoon",
                "attestations": {
                    "slsa_level": 3,
                    "source_ref": f"refs/tags/payments-stage-v2.5.{seed}",
                    "test_run_id": f"tr-{pay_stage_id}",
                },
                "features": {"privileged": False, "db_migration": False, "public_api": False},
                "sbom": [{"package": "pay-stage-core", "severity": "low", "license": "Apache-2.0"}],
                "exception_tokens": [],
                "rollout_impact": 4 + seed,
            },
            {
                "id": cat_stage_id,
                "service": "catalog",
                "env": "stage",
                "version": f"5.3.{seed}",
                "digest": cat_stage_digest,
                "base_image": "debian:12@sha256:base-cat-stage",
                "built_at": "2026-07-03T21:00:00Z",
                "signer": "sigstore-root",
                "requested_window": "stage-afternoon",
                "attestations": {
                    "slsa_level": 2,
                    "source_ref": f"refs/tags/catalog-stage-v5.3.{seed}",
                    "test_run_id": f"tr-{cat_stage_id}",
                },
                "features": {"privileged": False, "db_migration": False, "public_api": False},
                "sbom": [{"package": "catalog-stage-cache", "severity": "medium", "license": "MIT"}],
                "exception_tokens": [],
                "rollout_impact": 70 + seed,
                "requires": [{"service": "payments", "env": "stage", "min_version": "2.5.0"}],
            },
            {
                "id": sea_stage_id,
                "service": "search",
                "env": "stage",
                "version": f"2.0.{seed}",
                "digest": sea_stage_digest,
                "base_image": "debian:12@sha256:base-sea-stage",
                "built_at": "2026-07-03T22:00:00Z",
                "signer": "labs-ca",
                "requested_window": "stage-afternoon",
                "attestations": {
                    "slsa_level": 2,
                    "source_ref": f"refs/tags/search-stage-v2.0.{seed}",
                    "test_run_id": f"tr-{sea_stage_id}",
                },
                "features": {"privileged": False, "db_migration": False, "public_api": False},
                "sbom": [{"package": "search-stage-core", "severity": "low", "license": "Apache-2.0"}],
                "exception_tokens": [],
                "rollout_impact": 84 + seed,
                "conflicts_with": [{"service": "payments", "env": "stage"}],
            },
        ]
    )
    runs.extend(
        [
            {
                "id": f"tr-{pay_stage_id}",
                "status": "passed",
                "digest": pay_stage_digest,
                "source_ref": f"refs/tags/payments-stage-v2.5.{seed}",
                "coverage": 92,
                "flaky": False,
            },
            {
                "id": f"tr-{cat_stage_id}",
                "status": "passed",
                "digest": cat_stage_digest,
                "source_ref": f"refs/tags/catalog-stage-v5.3.{seed}",
                "coverage": 86,
                "flaky": False,
            },
            {
                "id": f"tr-{sea_stage_id}",
                "status": "passed",
                "digest": sea_stage_digest,
                "source_ref": f"refs/tags/search-stage-v2.0.{seed}",
                "coverage": 82,
                "flaky": False,
            },
        ]
    )
    return bundle


def write_bundle(bundle, input_dir):
    input_dir.mkdir(parents=True, exist_ok=True)
    write_json(input_dir / "policy.json", bundle["policy"])
    write_json(input_dir / "runtime_state.json", bundle["runtime"])
    write_json(input_dir / "test_runs.json", bundle["tests"])
    write_json(input_dir / "exceptions.json", bundle["exceptions"])
    write_json(input_dir / "candidates.json", bundle["candidates"])


def temporal_dependency_bundle(seed):
    bundle = copy.deepcopy(load_bundle(PUBLIC_INPUT))
    bundle["policy"]["envs"]["stage"]["max_approvals"] = 2
    bundle["policy"]["windows"].append(
        {
            "id": f"stage-early-{seed}",
            "env": "stage",
            "starts_at": "2026-07-04T11:00:00Z",
            "capacity": 1,
            "risk_budget": 200,
            "max_db_migrations": 1,
        }
    )

    pay_id = f"pay-future-{seed}"
    pay_digest = f"sha256:{pay_id}"
    cat_id = f"cat-early-{seed}"
    cat_digest = f"sha256:{cat_id}"
    bundle["candidates"]["candidates"].extend(
        [
            {
                "id": pay_id,
                "service": "payments",
                "env": "stage",
                "version": f"3.0.{seed}",
                "digest": pay_digest,
                "base_image": "ubuntu:22.04@sha256:base-pay-stage-future",
                "built_at": "2026-07-03T19:00:00Z",
                "signer": "payments-ca",
                "requested_window": "stage-afternoon",
                "attestations": {
                    "slsa_level": 3,
                    "source_ref": f"refs/tags/payments-future-v3.0.{seed}",
                    "test_run_id": f"tr-{pay_id}",
                },
                "features": {"privileged": False, "db_migration": False, "public_api": False},
                "sbom": [{"package": "pay-future-core", "severity": "low", "license": "Apache-2.0"}],
                "exception_tokens": [],
                "rollout_impact": 65 + seed,
            },
            {
                "id": cat_id,
                "service": "catalog",
                "env": "stage",
                "version": f"6.0.{seed}",
                "digest": cat_digest,
                "base_image": "debian:12@sha256:base-cat-stage-early",
                "built_at": "2026-07-03T18:00:00Z",
                "signer": "sigstore-root",
                "requested_window": f"stage-early-{seed}",
                "attestations": {
                    "slsa_level": 2,
                    "source_ref": f"refs/tags/catalog-early-v6.0.{seed}",
                    "test_run_id": f"tr-{cat_id}",
                },
                "features": {"privileged": False, "db_migration": False, "public_api": False},
                "sbom": [{"package": "catalog-early-cache", "severity": "low", "license": "MIT"}],
                "exception_tokens": [],
                "rollout_impact": 160 + seed,
                "requires": [{"service": "payments", "env": "stage", "min_version": "3.0.0"}],
            },
        ]
    )
    bundle["tests"]["runs"].extend(
        [
            {
                "id": f"tr-{pay_id}",
                "status": "passed",
                "digest": pay_digest,
                "source_ref": f"refs/tags/payments-future-v3.0.{seed}",
                "coverage": 93,
                "flaky": False,
            },
            {
                "id": f"tr-{cat_id}",
                "status": "passed",
                "digest": cat_digest,
                "source_ref": f"refs/tags/catalog-early-v6.0.{seed}",
                "coverage": 87,
                "flaky": False,
            },
        ]
    )
    return bundle


def temporal_dependency_actual_expected(tmp_path):
    cases = []
    for seed in range(4):
        case_dir = tmp_path / f"temporal-case-{seed}"
        bundle = temporal_dependency_bundle(seed)
        write_bundle(bundle, case_dir)
        actual = run_agent(case_dir, tmp_path / f"temporal-run-{seed}")
        cases.append((seed, bundle, actual, expected_output(bundle)))
    return cases


def test_public_input_files_are_unchanged():
    """Verifies the public policy bundle has not been changed or simplified."""
    assert SCRIPT.exists(), "expected /app/task_file/adjudicate.js to exist"
    for name, expected in PUBLIC_HASHES.items():
        assert sha256(PUBLIC_INPUT / name) == expected


def test_public_output_schema_and_candidate_partition(tmp_path):
    """Checks the top-level schema and that each candidate appears exactly once."""
    bundle, actual, _ = public_actual_expected(tmp_path)
    assert_schema_and_partition(actual, bundle)


def test_public_selected_rows_match_reference(tmp_path):
    """Checks selected rows, ordering, values, risk scores, and warnings."""
    _, actual, expected = public_actual_expected(tmp_path)
    assert actual["selected"] == expected["selected"]


def test_public_rejected_rows_match_reference(tmp_path):
    """Checks rejected rows and ordered additive rejection reasons."""
    _, actual, expected = public_actual_expected(tmp_path)
    assert actual["rejected"] == expected["rejected"]


def test_public_deferred_rows_use_reason_lists(tmp_path):
    """Checks deferred rows use candidate_id plus a single-item reasons list."""
    _, actual, expected = public_actual_expected(tmp_path)
    assert actual["deferred"] == expected["deferred"]
    assert all(set(row) == {"candidate_id", "reasons"} for row in actual["deferred"])
    assert all(isinstance(row["reasons"], list) and len(row["reasons"]) == 1 for row in actual["deferred"])


def test_public_summary_matches_selected_rows(tmp_path):
    """Checks summary counts, total value, total risk, and selected-row buckets."""
    _, actual, expected = public_actual_expected(tmp_path)
    assert actual["summary"] == expected["summary"]


def test_generated_variants_keep_valid_schema(tmp_path):
    """Checks generated compatible bundles keep the documented output shape."""
    for bundle, actual, _ in generated_actual_expected(tmp_path):
        assert_schema_and_partition(actual, bundle)


def test_generated_variants_select_reference_plans(tmp_path):
    """Checks generated compatible bundles choose the reference selected sets."""
    for _, actual, expected in generated_actual_expected(tmp_path):
        assert actual["selected"] == expected["selected"]


def test_generated_variants_reject_reference_candidates(tmp_path):
    """Checks generated compatible bundles emit the reference rejection reasons."""
    for _, actual, expected in generated_actual_expected(tmp_path):
        assert actual["rejected"] == expected["rejected"]


def test_generated_variants_defer_reference_candidates(tmp_path):
    """Checks generated compatible bundles emit the reference deferral reasons."""
    for _, actual, expected in generated_actual_expected(tmp_path):
        assert actual["deferred"] == expected["deferred"]


def test_generated_variants_summarize_reference_plans(tmp_path):
    """Checks generated compatible bundles emit the reference summary totals."""
    for _, actual, expected in generated_actual_expected(tmp_path):
        assert actual["summary"] == expected["summary"]


def test_generated_variants_enforce_rollout_requires_and_conflicts(tmp_path):
    """Checks generated bundles honor optional requires and conflicts_with plan rules."""
    for seed, (bundle, actual, expected) in enumerate(generated_actual_expected(tmp_path)):
        assert actual["selected"] == expected["selected"]
        selected_ids = {row["candidate_id"] for row in actual["selected"]}
        assert f"cat-stage-{seed}" in selected_ids
        assert f"pay-stage-{seed}" in selected_ids
        assert f"sea-stage-{seed}" not in selected_ids


def test_temporal_requires_reject_future_window_satisfaction(tmp_path):
    """Checks an earlier deployment cannot rely on a required service selected later."""
    for seed, _, actual, expected in temporal_dependency_actual_expected(tmp_path):
        assert actual["selected"] == expected["selected"]
        selected_ids = {row["candidate_id"] for row in actual["selected"]}
        assert f"cat-early-{seed}" not in selected_ids
        assert f"pay-future-{seed}" in selected_ids


def test_temporal_requires_summary_and_deferrals(tmp_path):
    """Checks time-aware dependency variants keep expected summaries and deferrals."""
    for _, _, actual, expected in temporal_dependency_actual_expected(tmp_path):
        assert actual["deferred"] == expected["deferred"]
        assert actual["summary"] == expected["summary"]


def tie_case_actual_expected(tmp_path):
    bundle = variant_bundle(7)
    for window in bundle["policy"]["windows"]:
        if window["id"] == "prod-early":
            window["capacity"] = 1
            window["risk_budget"] = 500
        if window["id"] == "prod-late":
            window["capacity"] = 1
            window["risk_budget"] = 500
    case_dir = tmp_path / "tie-case"
    write_bundle(bundle, case_dir)
    actual = run_agent(case_dir, tmp_path / "tie-run")
    expected = expected_output(bundle)
    return bundle, actual, expected


def test_tie_case_schema_and_partition(tmp_path):
    """Checks the tie case still partitions every candidate exactly once."""
    bundle, actual, _ = tie_case_actual_expected(tmp_path)
    assert_schema_and_partition(actual, bundle)


def test_complete_set_tie_break_selects_reference_plan(tmp_path):
    """Checks complete-set tie-breaks select the reference candidate ids."""
    _, actual, expected = tie_case_actual_expected(tmp_path)
    assert actual["selected"] == expected["selected"]


def test_deferred_lower_ranked_candidate_reason(tmp_path):
    """Checks same service/environment losers use lower_ranked_candidate."""
    _, actual, expected = tie_case_actual_expected(tmp_path)
    assert actual["deferred"] == expected["deferred"]
    reasons = [reason for row in actual["deferred"] for reason in row["reasons"]]
    assert "lower_ranked_candidate" in reasons


def test_deferred_capacity_or_budget_reason(tmp_path):
    """Checks otherwise eligible unselected rows use capacity_or_budget."""
    _, actual, expected = tie_case_actual_expected(tmp_path)
    assert actual["deferred"] == expected["deferred"]
    reasons = [reason for row in actual["deferred"] for reason in row["reasons"]]
    assert "capacity_or_budget" in reasons
