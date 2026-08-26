import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path


APP = Path(os.environ.get("APP_DIR", "/app"))
SRC = APP / "keyring_cutover_gate.go"
BIN = APP / "keyring_cutover_gate"
PUBLIC_REQUEST = APP / "input_data" / "request.json"
PUBLIC_CATALOG = APP / "input_data" / "catalog.json"
PUBLIC_OUTPUT = APP / "output_data" / "cutover_plan.json"

PUBLIC_REQUEST_SHA = "dc2126c8fb8ff9fe933d7cc03c623743b8af3f7aa6db9f29fb18fd3059c040c3"
PUBLIC_CATALOG_SHA = "aad304ba0ad6414fda63f90f41b630df38b59186124a9ba2f2a70f25cdc3c5ac"


def read_json(path):
    return json.loads(Path(path).read_text())


def read_json_pairs(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=list)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def usable(bundle, request):
    return (
        bundle["runtime"] == request["target_runtime"]
        and bundle["track"] in request["allowed_tracks"]
        and bundle["issuer"] not in set(request["revoked_issuers"])
    )


def group_bundles(bundles):
    grouped = {}
    for bundle in bundles:
        key = bundle["slot"] if bundle["slot"] is not None else f"__{bundle['id']}"
        grouped.setdefault(key, []).append(bundle)

    def weight(item):
        key, rows = item
        relevant = 0
        for row in rows:
            relevant += len(row["claims"]) + len(row["prerequisites"]) + len(row["excludes"])
        return (-relevant, -len(rows), key)

    groups = []
    for key, rows in sorted(grouped.items(), key=weight):
        groups.append((key, sorted(rows, key=lambda row: row["id"])))
    return groups


def claim_strengths(selected, baseline):
    strengths = {row["name"]: row["strength"] for row in baseline}
    for bundle in selected:
        for row in bundle["claims"]:
            strengths[row["name"]] = max(strengths.get(row["name"], 0), row["strength"])
    return strengths


def selected_set_valid(selected, request):
    families = [bundle["family"] for bundle in selected]
    if len(families) != len(set(families)):
        return False

    slots = [bundle["slot"] for bundle in selected if bundle["slot"] is not None]
    if len(slots) != len(set(slots)):
        return False

    if sum(bundle["footprint_kb"] for bundle in selected) > request["max_total_footprint_kb"]:
        return False

    counts = Counter(bundle["issuer"] for bundle in selected)
    for issuer, count in counts.items():
        cap = request["issuer_caps"].get(issuer)
        if cap is not None and count > cap:
            return False

    strengths = claim_strengths(selected, request["baseline_claims"])
    for bundle in selected:
        for prereq in bundle["prerequisites"]:
            if strengths.get(prereq["name"], 0) < prereq["min_strength"]:
                return False
        for token in bundle["excludes"]:
            for other in selected:
                if other["id"] == bundle["id"]:
                    continue
                if other["family"] == token:
                    return False
                if any(claim["name"] == token for claim in other["claims"]):
                    return False
    return True


def canonical_activation_order(selected, baseline):
    remaining = {bundle["id"]: bundle for bundle in selected}
    strengths = {row["name"]: row["strength"] for row in baseline}
    order = []
    while remaining:
        ready = []
        for bundle_id, bundle in remaining.items():
            if all(strengths.get(prereq["name"], 0) >= prereq["min_strength"] for prereq in bundle["prerequisites"]):
                ready.append(bundle_id)
        if not ready:
            return None
        bundle_id = min(ready)
        bundle = remaining.pop(bundle_id)
        order.append(bundle_id)
        for row in bundle["claims"]:
            strengths[row["name"]] = max(strengths.get(row["name"], 0), row["strength"])
    return order


def satisfied_required_count(request, strengths):
    return sum(
        1
        for row in request["required_claims"]
        if strengths.get(row["name"], 0) >= row["min_strength"]
    )


def assert_key_order(actual_pairs, expected_keys):
    assert [key for key, _ in actual_pairs] == expected_keys


def assert_output_order(output_path, request):
    top = read_json_pairs(output_path)
    assert_key_order(top, ["generated_at", "status", "selected_bundle_ids", "summary"])
    top_map = {key: value for key, value in top}
    assert isinstance(top_map["selected_bundle_ids"], list)

    summary_pairs = top_map["summary"]
    assert_key_order(
        summary_pairs,
        ["total_footprint_kb", "total_risk", "claim_strengths", "missing_claims"],
    )
    summary_map = {key: value for key, value in summary_pairs}
    assert isinstance(summary_map["missing_claims"], list)

    claim_rows = summary_map["claim_strengths"]
    assert len(claim_rows) == len(request["required_claims"])
    for row in claim_rows:
        assert_key_order(row, ["name", "strength"])


def run_case(request, catalog):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        request_path = tmp / "request.json"
        catalog_path = tmp / "catalog.json"
        output_path = tmp / "cutover_plan.json"
        request_path.write_text(json.dumps(request, indent=2) + "\n")
        catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
        subprocess.run([str(BIN), str(request_path), str(catalog_path), str(output_path)], check=True)
        assert_output_order(output_path, request)
        return read_json(output_path)


def build_binary():
    assert SRC.exists(), f"missing source file: {SRC}"
    subprocess.run(["go", "build", "-o", str(BIN), str(SRC)], check=True)
    assert BIN.exists(), f"missing binary: {BIN}"


def base_request():
    return read_json(PUBLIC_REQUEST)


def base_catalog():
    return read_json(PUBLIC_CATALOG)


def add_bundle(catalog, bundle):
    catalog["bundles"].append(bundle)


def bundle_conflict_tokens(bundle):
    tokens = set(bundle["excludes"])
    tokens.add(bundle["family"])
    for row in bundle["claims"]:
        tokens.add(row["name"])
    return tokens


def conflicts_with_selected(bundle, selected):
    bundle_tokens = bundle_conflict_tokens(bundle)
    for other in selected:
        other_tokens = bundle_conflict_tokens(other)
        if set(bundle["excludes"]) & other_tokens:
            return True
        if set(other["excludes"]) & bundle_tokens:
            return True
    return False


def suffix_claim_bounds(groups):
    suffix = [dict() for _ in range(len(groups) + 1)]
    for index in range(len(groups) - 1, -1, -1):
        merged = dict(suffix[index + 1])
        _, bundles = groups[index]
        local = {}
        for bundle in bundles:
            for row in bundle["claims"]:
                local[row["name"]] = max(local.get(row["name"], 0), row["strength"])
        for name, strength in local.items():
            merged[name] = max(merged.get(name, 0), strength)
        suffix[index] = merged
    return suffix


def canonical_output(request, catalog):
    bundles = [bundle for bundle in catalog["bundles"] if usable(bundle, request)]
    groups = group_bundles(bundles)
    suffix_bounds = suffix_claim_bounds(groups)

    best_score = None
    best_order = None
    best_subset = None

    def upper_bound_satisfied(current_strengths, index):
        future = suffix_bounds[index]
        return sum(
            1
            for row in request["required_claims"]
            if max(current_strengths.get(row["name"], 0), future.get(row["name"], 0)) >= row["min_strength"]
        )

    def selected_prereqs_still_possible(selected, current_strengths, index):
        future = suffix_bounds[index]
        for bundle in selected:
            for prereq in bundle["prerequisites"]:
                if max(current_strengths.get(prereq["name"], 0), future.get(prereq["name"], 0)) < prereq["min_strength"]:
                    return False
        return True

    def search(index, selected, used_families, signer_counts, total_footprint):
        nonlocal best_score, best_order, best_subset

        if total_footprint > request["max_total_footprint_kb"]:
            return

        for issuer, count in signer_counts.items():
            cap = request["issuer_caps"].get(issuer)
            if cap is not None and count > cap:
                return

        strengths = claim_strengths(selected, request["baseline_claims"])
        if not selected_prereqs_still_possible(selected, strengths, index):
            return

        upper_satisfied = upper_bound_satisfied(strengths, index)
        if best_score is not None and upper_satisfied < best_score[0]:
            return

        if index == len(groups):
            if not selected_set_valid(selected, request):
                return
            order = canonical_activation_order(selected, request["baseline_claims"])
            if order is None:
                return
            score = (
                satisfied_required_count(request, strengths),
                -sum(bundle["risk"] for bundle in selected),
                -sum(bundle["footprint_kb"] for bundle in selected),
                -len(selected),
            )
            if best_score is None or score > best_score or (score == best_score and order < best_order):
                best_score = score
                best_order = order
                best_subset = [bundle for bundle in selected]
            return

        _, options = groups[index]
        search(index + 1, selected, used_families, signer_counts, total_footprint)

        for bundle in options:
            if bundle["family"] in used_families:
                continue
            if conflicts_with_selected(bundle, selected):
                continue
            issuer = bundle["issuer"]
            cap = request["issuer_caps"].get(issuer)
            if cap is not None and signer_counts.get(issuer, 0) >= cap:
                continue
            selected.append(bundle)
            used_families.add(bundle["family"])
            signer_counts[issuer] = signer_counts.get(issuer, 0) + 1
            search(index + 1, selected, used_families, signer_counts, total_footprint + bundle["footprint_kb"])
            signer_counts[issuer] -= 1
            if signer_counts[issuer] == 0:
                del signer_counts[issuer]
            used_families.remove(bundle["family"])
            selected.pop()

    search(0, [], set(), {}, 0)

    assert best_subset is not None
    strengths = claim_strengths(best_subset, request["baseline_claims"])
    claim_rows = [
        {"name": row["name"], "strength": strengths.get(row["name"], 0)}
        for row in request["required_claims"]
    ]
    missing_claims = [
        row["name"]
        for row in request["required_claims"]
        if strengths.get(row["name"], 0) < row["min_strength"]
    ]
    return {
        "generated_at": request["generated_at"],
        "status": "ready" if not missing_claims else "gap",
        "selected_bundle_ids": best_order,
        "summary": {
            "total_footprint_kb": sum(bundle["footprint_kb"] for bundle in best_subset),
            "total_risk": sum(bundle["risk"] for bundle in best_subset),
            "claim_strengths": claim_rows,
            "missing_claims": missing_claims,
        },
    }


def make_bundle(
    bundle_id,
    family,
    version,
    runtime,
    track,
    issuer,
    footprint_kb,
    risk,
    slot,
    claims,
    prerequisites,
    excludes,
):
    return {
        "id": bundle_id,
        "family": family,
        "version": version,
        "runtime": runtime,
        "track": track,
        "issuer": issuer,
        "footprint_kb": footprint_kb,
        "risk": risk,
        "slot": slot,
        "claims": [{"name": name, "strength": strength} for name, strength in claims],
        "prerequisites": [{"name": name, "min_strength": strength} for name, strength in prerequisites],
        "excludes": list(excludes),
    }


def generated_case(seed):
    request = {
        "generated_at": f"2026-07-13T00:00:{seed:02d}Z",
        "rollout_id": f"rollout-generated-{seed}",
        "target_runtime": "linux-amd64",
        "allowed_tracks": ["stable", "canary"] if seed % 2 == 0 else ["stable", "lts"],
        "revoked_issuers": ["revoked-ca"] if seed % 3 else ["revoked-ca", "west-ca"],
        "max_total_footprint_kb": 104 + seed * 6,
        "issuer_caps": {
            "north-ca": 1 + (seed % 3 != 1),
            "east-ca": 1 + (seed % 4 == 0),
            "west-ca": 1,
        },
        "baseline_claims": [
            {"name": "clock-sync", "strength": 2},
            {"name": "audit-log", "strength": 1 + (seed % 2)},
            {"name": "operator-presence", "strength": 1 + (seed % 3 == 0)},
        ],
        "required_claims": [
            {"name": "verify-core", "min_strength": 6},
            {"name": "tsa", "min_strength": 5},
            {"name": "revocation", "min_strength": 5},
            {"name": "provenance", "min_strength": 4},
            {"name": "legacy-jar", "min_strength": 3 if seed % 2 else 2},
            {"name": "sbom", "min_strength": 4 if seed % 3 else 5},
            {"name": "provenance", "min_strength": 5 if seed % 2 else 4},
            {"name": "quorum", "min_strength": 3 + (seed % 2)},
        ],
    }

    bundles = []
    family_specs = [
        ("core-verifier", "core", [("verify-core", 6), ("provenance", 1)], [("clock-sync", 2)]),
        ("tsa-chain", "tsa", [("tsa", 5)], [("verify-core", 5)]),
        ("crl-pack", "revoke", [("revocation", 5)], [("verify-core", 5)]),
        ("ocsp-pack", "ocsp", [("revocation", 4), ("sbom", 2)], [("verify-core", 5)]),
        ("prov-pack", "prov", [("provenance", 4)], [("tsa", 5)]),
        ("legacy-bridge", "legacy", [("legacy-jar", 3)], [("verify-core", 5)]),
        ("sbom-pack", "meta", [("sbom", 4)], [("verify-core", 5)]),
        ("quorum-pack", "quorum", [("quorum", 4)], [("verify-core", 6), ("operator-presence", 1)]),
    ]
    issuers = ["north-ca", "east-ca", "south-ca", "west-ca"]
    tracks = ["stable", "canary", "lts"]

    for index, (family, slot, claims, prereqs) in enumerate(family_specs):
        for variant in range(3):
            bundle_id = f"{family[:4]}-{seed}-{variant}"
            issuer = issuers[(index + variant + seed) % len(issuers)]
            track = tracks[(seed + variant) % len(tracks)]
            runtime = "linux-amd64" if variant < 2 else ("linux-arm64" if index % 2 == 0 else "linux-amd64")
            footprint = 13 + index * 4 + variant * 4 + (seed % 4)
            risk = 2 + (index * 2 + variant + seed) % 7
            local_claims = list(claims)
            if family == "core-verifier" and variant == 1:
                local_claims = [("verify-core", 5), ("provenance", 4)]
            if family == "core-verifier" and variant == 2:
                local_claims = [("verify-core", 6), ("sbom", 1)]
            if family == "sbom-pack" and variant == 2:
                local_claims = [("sbom", 5)]
            if family == "ocsp-pack" and variant == 1:
                local_claims = [("revocation", 5), ("sbom", 3)]
            if family == "quorum-pack" and variant == 1:
                local_claims = [("quorum", 3), ("provenance", 2)]
            local_prereqs = list(prereqs)
            excludes = []
            if family == "legacy-bridge" and variant == 2:
                excludes = ["crl-pack"]
            if family == "prov-pack" and variant == 1:
                local_prereqs = [("tsa", 4)]
            if family == "sbom-pack" and variant == 1:
                excludes = ["legacy-jar"]
            if family == "ocsp-pack" and variant == 2:
                excludes = ["quorum"]
            if family == "quorum-pack" and variant == 2:
                local_prereqs = [("verify-core", 5), ("operator-presence", 1)]
            bundles.append(
                make_bundle(
                    bundle_id,
                    family,
                    f"{1 + variant}.{seed}.{index}",
                    runtime,
                    track,
                    issuer,
                    footprint,
                    risk,
                    slot,
                    local_claims,
                    local_prereqs,
                    excludes,
                )
            )

    for extra in range(8):
        track = tracks[(seed + extra + 1) % len(tracks)]
        issuer = issuers[(seed + extra) % len(issuers)]
        claims = [("audit-log", 2 + extra % 2)] if extra % 2 == 0 else [("provenance", 2 + extra % 3)]
        prereqs = [] if extra % 3 else [("verify-core", 5)]
        excludes = ["sbom"] if extra == 4 else []
        if extra == 5:
            claims = [("operator-presence", 2), ("quorum", 2)]
            prereqs = [("verify-core", 5)]
        if extra == 6:
            claims = [("legacy-jar", 2), ("sbom", 3)]
            prereqs = [("tsa", 4)]
            excludes = ["crl-pack"]
        if extra == 7:
            claims = [("revocation", 3), ("provenance", 4)]
            prereqs = [("verify-core", 6)]
            excludes = ["legacy-jar"]
        bundles.append(
            make_bundle(
                f"addon-{seed}-{extra}",
                f"addon-family-{extra}",
                f"0.{seed}.{extra}",
                "linux-amd64",
                track,
                issuer,
                10 + extra * 3,
                1 + (seed + extra) % 5,
                None,
                claims,
                prereqs,
                excludes,
            )
        )

    catalog = {"bundles": bundles}
    return request, catalog


def pressure_case(seed):
    request, catalog = generated_case(seed)
    request["allowed_tracks"] = ["stable", "canary", "lts"]
    request["max_total_footprint_kb"] = min(request["max_total_footprint_kb"], 112)
    request["issuer_caps"]["north-ca"] = 1
    request["issuer_caps"]["east-ca"] = 1
    request["required_claims"].extend(
        [
            {"name": "sbom", "min_strength": 5},
            {"name": "provenance", "min_strength": 5},
            {"name": "quorum", "min_strength": 4},
            {"name": "revocation", "min_strength": 5},
        ]
    )

    add_bundle(
        catalog,
        make_bundle(
            f"alpha-tie-{seed}",
            "alpha-tie",
            "1.0.0",
            "linux-amd64",
            "stable",
            "south-ca",
            14,
            1,
            None,
            [("mirror-claim", 2)],
            [("verify-core", 6)],
            [],
        ),
    )
    add_bundle(
        catalog,
        make_bundle(
            f"beta-tie-{seed}",
            "beta-tie",
            "1.0.0",
            "linux-amd64",
            "stable",
            "south-ca",
            14,
            1,
            None,
            [("mirror-claim", 2)],
            [("verify-core", 6)],
            [],
        ),
    )
    request["required_claims"].append({"name": "mirror-claim", "min_strength": 2})

    add_bundle(
        catalog,
        make_bundle(
            f"issuer-trap-{seed}",
            "issuer-trap",
            "1.0.0",
            "linux-amd64",
            "stable",
            "north-ca",
            15,
            1,
            None,
            [("provenance", 5), ("sbom", 5)],
            [("tsa", 5)],
            ["quorum"],
        ),
    )
    add_bundle(
        catalog,
        make_bundle(
            f"exclude-trap-{seed}",
            "exclude-trap",
            "1.0.0",
            "linux-amd64",
            "canary",
            "east-ca",
            13,
            1,
            None,
            [("quorum", 4)],
            [("verify-core", 6)],
            ["provenance"],
        ),
    )

    return request, catalog


def impossible_gap_case(seed):
    request, catalog = generated_case(seed)
    request["allowed_tracks"] = ["stable"]
    request["revoked_issuers"] = ["revoked-ca", "south-ca"]
    request["max_total_footprint_kb"] = 18 + (seed % 3)
    request["issuer_caps"] = {"north-ca": 1, "east-ca": 1, "west-ca": 0}
    request["required_claims"] = [
        {"name": "verify-core", "min_strength": 7},
        {"name": "tsa", "min_strength": 6},
        {"name": "revocation", "min_strength": 6},
        {"name": "quorum", "min_strength": 5},
    ]
    catalog = {
        "bundles": [
            make_bundle(
                f"impossible-prov-{seed}",
                "impossible-prov",
                "1.0.0",
                "linux-amd64",
                "stable",
                "north-ca",
                16,
                1,
                None,
                [("provenance", 2)],
                [("tsa", 6)],
                [],
            ),
            make_bundle(
                f"impossible-tsa-{seed}",
                "impossible-tsa",
                "1.0.0",
                "linux-amd64",
                "stable",
                "east-ca",
                17,
                1,
                None,
                [("tsa", 4)],
                [("verify-core", 6)],
                [],
            ),
        ]
    }
    return request, catalog


def test_public_inputs_are_unchanged():
    assert sha256(PUBLIC_REQUEST) == PUBLIC_REQUEST_SHA
    assert sha256(PUBLIC_CATALOG) == PUBLIC_CATALOG_SHA


def test_solution_builds_and_public_case_matches_oracle():
    build_binary()
    shutil.rmtree(PUBLIC_OUTPUT.parent, ignore_errors=True)
    PUBLIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(BIN), str(PUBLIC_REQUEST), str(PUBLIC_CATALOG), str(PUBLIC_OUTPUT)], check=True)
    assert_output_order(PUBLIC_OUTPUT, base_request())
    expected = canonical_output(base_request(), base_catalog())
    assert read_json(PUBLIC_OUTPUT) == expected
    assert sha256(PUBLIC_REQUEST) == PUBLIC_REQUEST_SHA
    assert sha256(PUBLIC_CATALOG) == PUBLIC_CATALOG_SHA


def test_gap_case_can_select_nothing():
    request = base_request()
    request["allowed_tracks"] = ["stable"]
    request["max_total_footprint_kb"] = 18
    catalog = {
        "bundles": [
            make_bundle(
                "tiny-prov",
                "tiny-prov",
                "1.0.0",
                "linux-amd64",
                "stable",
                "south-ca",
                16,
                1,
                None,
                [("provenance", 2)],
                [("tsa", 5)],
                [],
            )
        ]
    }
    build_binary()
    assert run_case(request, catalog) == canonical_output(request, catalog)


def test_gap_output_uses_empty_arrays_not_null():
    request, catalog = impossible_gap_case(31)
    build_binary()
    actual = run_case(request, catalog)
    expected = canonical_output(request, catalog)
    assert actual == expected
    assert actual["status"] == "gap"
    assert actual["selected_bundle_ids"] == []
    assert isinstance(actual["selected_bundle_ids"], list)
    assert isinstance(actual["summary"]["missing_claims"], list)
    assert len(actual["summary"]["missing_claims"]) == len(request["required_claims"])


def test_canonical_order_and_family_rule():
    request = {
        "generated_at": "2026-07-13T03:00:00Z",
        "rollout_id": "tie-case",
        "target_runtime": "linux-amd64",
        "allowed_tracks": ["stable"],
        "revoked_issuers": [],
        "max_total_footprint_kb": 90,
        "issuer_caps": {"north-ca": 2},
        "baseline_claims": [{"name": "clock-sync", "strength": 2}],
        "required_claims": [
            {"name": "verify-core", "min_strength": 5},
            {"name": "tsa", "min_strength": 4},
        ],
    }
    catalog = {
        "bundles": [
            make_bundle("b-core", "core", "1.0.0", "linux-amd64", "stable", "north-ca", 20, 3, "core", [("verify-core", 5)], [("clock-sync", 2)], []),
            make_bundle("a-tsa", "tsa", "1.0.0", "linux-amd64", "stable", "south-ca", 20, 3, "tsa", [("tsa", 4)], [("verify-core", 5)], []),
            make_bundle("c-tsa", "tsa", "1.0.1", "linux-amd64", "stable", "south-ca", 20, 3, "tsa", [("tsa", 4)], [("verify-core", 5)], []),
        ]
    }
    build_binary()
    actual = run_case(request, catalog)
    expected = canonical_output(request, catalog)
    assert actual == expected
    assert actual["selected_bundle_ids"] == ["b-core", "a-tsa"]


def test_duplicate_required_rows_and_excludes_by_claim():
    request = {
        "generated_at": "2026-07-13T04:00:00Z",
        "rollout_id": "duplicate-rows-case",
        "target_runtime": "linux-amd64",
        "allowed_tracks": ["stable"],
        "revoked_issuers": [],
        "max_total_footprint_kb": 90,
        "issuer_caps": {"north-ca": 1, "east-ca": 1},
        "baseline_claims": [
            {"name": "clock-sync", "strength": 2},
            {"name": "operator-presence", "strength": 1},
        ],
        "required_claims": [
            {"name": "verify-core", "min_strength": 6},
            {"name": "provenance", "min_strength": 4},
            {"name": "provenance", "min_strength": 5},
            {"name": "quorum", "min_strength": 3},
        ],
    }
    catalog = {
        "bundles": [
            make_bundle("core-a", "core", "1.0.0", "linux-amd64", "stable", "north-ca", 22, 4, "core", [("verify-core", 6)], [("clock-sync", 2)], []),
            make_bundle("prov-a", "prov", "1.0.0", "linux-amd64", "stable", "east-ca", 18, 2, "prov", [("provenance", 5)], [("verify-core", 6)], []),
            make_bundle("quorum-a", "quorum", "1.0.0", "linux-amd64", "stable", "south-ca", 17, 1, "quorum", [("quorum", 3)], [("verify-core", 6), ("operator-presence", 1)], []),
            make_bundle("trap-a", "trap", "1.0.0", "linux-amd64", "stable", "south-ca", 16, 1, None, [("provenance", 4), ("quorum", 3)], [("verify-core", 6)], ["provenance"]),
        ]
    }
    build_binary()
    actual = run_case(request, catalog)
    expected = canonical_output(request, catalog)
    assert actual == expected
    assert actual["summary"]["missing_claims"] == []


def test_generated_variant_matrix():
    build_binary()
    for seed in range(1, 29):
        request, catalog = generated_case(seed)
        actual = run_case(request, catalog)
        expected = canonical_output(request, catalog)
        assert actual == expected


def test_hidden_global_pressure():
    build_binary()
    for seed in range(21, 29):
        request, catalog = pressure_case(seed)
        actual = run_case(request, catalog)
        expected = canonical_output(request, catalog)
        assert actual == expected


def test_generated_impossible_gap_matrix():
    build_binary()
    for seed in range(31, 37):
        request, catalog = impossible_gap_case(seed)
        actual = run_case(request, catalog)
        expected = canonical_output(request, catalog)
        assert actual == expected
        assert actual["selected_bundle_ids"] == []
        assert actual["status"] == "gap"
