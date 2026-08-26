"""Verification for cargo feature resolution reconciler (Go featrecon)."""

from __future__ import annotations

import binascii
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPORT_PATH = Path("/app/build/feature_resolution_report.json")
REPORT_FIRST = Path("/logs/verifier/report_first.json")
REPORT_PERTURBED = Path("/logs/verifier/report_perturbed.json")
VERIFIER_DIR = Path("/logs/verifier")
CAPTURES_DIR = Path("/app/crate-captures")
MANIFEST_PATH = CAPTURES_DIR / "manifest.json"
SCHEMA_PATH = Path("/app/feature-policy/output_schema.json")
APP_DIR = Path("/app")

IMMUTABLE_SHA256: dict[str, str] = {}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_digest(scenarios: list[str]) -> str:
    h = hashlib.sha256()
    h.update(MANIFEST_PATH.read_bytes())
    for sid in scenarios:
        h.update((CAPTURES_DIR / f"{sid}.json").read_bytes())
    return h.hexdigest()


def _capture_chain_tail(scenarios: list[str], capture_digest: str) -> str:
    chain = bytes.fromhex(capture_digest)
    for sid in scenarios:
        h = hashlib.sha256()
        h.update(chain)
        h.update((CAPTURES_DIR / f"{sid}.json").read_bytes())
        chain = h.digest()
    return chain.hex()


def _manifest_payload_len() -> int:
    return len(MANIFEST_PATH.read_bytes())


def _bundled_payload_len(scenarios: list[str]) -> int:
    return sum(len((CAPTURES_DIR / f"{sid}.json").read_bytes()) for sid in scenarios)


def _payload_len_le(total: int) -> str:
    return (total & 0xFFFFFFFF).to_bytes(4, "little").hex()


def _scenario_payload_digest(scenario_id: str) -> str:
    return hashlib.sha256((CAPTURES_DIR / f"{scenario_id}.json").read_bytes()).hexdigest()


def _scenario_payload_crc32(scenario_id: str) -> str:
    data = (CAPTURES_DIR / f"{scenario_id}.json").read_bytes()
    return format(binascii.crc32(data) & 0xFFFFFFFF, "08x")


def _scenario_payload_len(scenario_id: str) -> int:
    return len((CAPTURES_DIR / f"{scenario_id}.json").read_bytes())


def _parse_semver(v: str) -> tuple[int, int, int]:
    parts = [0, 0, 0]
    seg = 0
    num = 0
    has = False
    for ch in v:
        if ch.isdigit():
            num = num * 10 + int(ch)
            has = True
            continue
        if has and seg < 3:
            parts[seg] = num
            seg += 1
            num = 0
            has = False
        if seg >= 2:
            break
    if has and seg < 3:
        parts[seg] = num
    return parts[0], parts[1], parts[2]


def _semver_less(a: str, b: str) -> bool:
    return _parse_semver(a) < _parse_semver(b)


def _sort_versions(versions: list[str]) -> list[str]:
    return sorted(versions, key=_parse_semver)


def _sort_features(features: list[str]) -> list[str]:
    return sorted(set(features))


def _union_features(a: list[str], b: list[str]) -> list[str]:
    return _sort_features(a + b)


def _conflict_severity(selected: str, rejected: list[str]) -> str:
    sm, _, _ = _parse_semver(selected)
    for r in rejected:
        rm, _, _ = _parse_semver(r)
        if sm != rm:
            return "hard"
    return "soft"


def _crate_key(crate: str, version: str) -> str:
    return f"{crate}:{version}"


def _filter_edges(edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    skipped = 0
    for edge in edges:
        eid = edge.get("edge_id") or ""
        if eid:
            if eid in seen:
                skipped += 1
                continue
            seen.add(eid)
        out.append(edge)
    return out, skipped


def _depth_cap(scenario: dict[str, Any]) -> int:
    cap = scenario.get("traversal_depth_cap")
    if isinstance(cap, int) and cap > 0:
        return cap
    return 64


def _source_label(
    crate: str,
    declared: dict[str, dict[str, Any]],
    members: set[str],
    from_pin: bool,
) -> str:
    if crate in declared:
        if crate in members:
            return "workspace_declared"
        return "declared"
    if from_pin:
        return "workspace"
    return "transitive"


def _filter_runtime_features(
    features: list[str], profile: str, tags: dict[str, Any]
) -> list[str]:
    if profile != "release":
        return _sort_features(features)
    dev = set(tags.get("dev_only_features") or [])
    out = [f for f in features if f not in dev]
    return _sort_features(out)


def _crate_on_runtime_set(crate_key: str, target: str, profile_mode: str) -> bool:
    if profile_mode == "host":
        return target in ("host", "any")
    if profile_mode == "target":
        return target in ("target", "any")
    return True


def _expand_aliases(features: list[str], aliases: dict[str, list[str]]) -> list[str]:
    if not aliases:
        return _sort_features(features)
    out: list[str] = []
    for feat in features:
        if feat in aliases:
            out = _union_features(out, aliases[feat])
        else:
            out.append(feat)
    return _sort_features(out)


def _edge_features(
    edge: dict[str, Any],
    ws_features: dict[str, list[str]],
    aliases: dict[str, list[str]],
) -> list[str]:
    feats = list(edge.get("features_requested") or [])
    if edge.get("default_features"):
        feats = _union_features(feats, edge.get("default_crate_features") or [])
    child = edge["child"]
    if child in ws_features:
        feats = _union_features(feats, ws_features[child])
    return _expand_aliases(feats, aliases)


def _resolve_graph(
    scenario: dict[str, Any],
    edges: list[dict[str, Any]],
    pins: dict[str, str],
    ws_features: dict[str, list[str]],
    declared: dict[str, dict[str, Any]],
    members: set[str],
    exclusions: set[str],
    aliases: dict[str, list[str]],
) -> dict[str, Any]:
    cap = _depth_cap(scenario)
    edges_by_parent: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        edges_by_parent.setdefault(edge["parent"], []).append(edge)
    for parent in edges_by_parent:
        edges_by_parent[parent] = sorted(
            edges_by_parent[parent],
            key=lambda e: (e["child"], e.get("edge_id", "")),
        )

    winners: dict[str, dict[str, Any]] = {}
    crates: dict[str, dict[str, Any]] = {}
    crate_targets: dict[str, str] = {}
    conflicts: dict[str, dict[str, Any]] = {}
    edges_traversed = 0
    frames_rejected = 0
    truncated_tail = 0
    conflict_rows_purged = 0

    def add_rejected(crate: str, selected: str, rejected: str, reason: str = "nearest") -> None:
        if rejected == selected:
            return
        key = f"{crate}\x00{selected}"
        if key not in conflicts:
            conflicts[key] = {
                "crate": crate,
                "selected_version": selected,
                "rejected_versions": [],
                "resolution_reason": reason,
                "severity": "soft",
            }
        entry = conflicts[key]
        if reason == "unified":
            entry["resolution_reason"] = "unified"
        if rejected not in entry["rejected_versions"]:
            entry["rejected_versions"].append(rejected)
            entry["rejected_versions"] = _sort_versions(entry["rejected_versions"])
            entry["severity"] = _conflict_severity(selected, entry["rejected_versions"])

    def register(
        crate: str,
        version: str,
        depth: int,
        parent_key: str,
        source: str,
        features: list[str],
        target_triple: str,
    ) -> str:
        nonlocal conflict_rows_purged
        ck = _crate_key(crate, version)
        prev = winners.get(crate)
        if prev is None:
            winners[crate] = {
                "version": version,
                "depth": depth,
                "parent_key": parent_key,
                "crate_key": ck,
                "source": source,
                "features": _sort_features(features),
            }
            crates[ck] = {
                "crate_key": ck,
                "crate": crate,
                "version": version,
                "depth": depth,
                "source": source,
                "active_features": _sort_features(features),
            }
            crate_targets[ck] = target_triple
            return ck

        if (
            depth == prev["depth"]
            and parent_key == prev["parent_key"]
            and version == prev["version"]
        ):
            merged = _union_features(prev["features"], features)
            if merged != prev["features"]:
                prev["features"] = merged
                crates[prev["crate_key"]]["active_features"] = merged
            return prev["crate_key"]

        contender = {
            "version": version,
            "depth": depth,
            "parent_key": parent_key,
            "crate_key": ck,
            "source": source,
            "features": _sort_features(features),
        }
        keep = prev
        if depth < prev["depth"]:
            keep = contender
            add_rejected(crate, version, prev["version"])
        elif depth > prev["depth"]:
            add_rejected(crate, prev["version"], version)
            return prev["crate_key"]
        elif parent_key < prev["parent_key"]:
            keep = contender
            add_rejected(crate, version, prev["version"])
        else:
            add_rejected(crate, prev["version"], version, "unified")
            return prev["crate_key"]

        if keep["crate_key"] != prev["crate_key"]:
            stale = [
                k
                for k, c in conflicts.items()
                if c["crate"] == crate and c["selected_version"] != keep["version"]
            ]
            for k in stale:
                del conflicts[k]
            conflict_rows_purged += len(stale)
            del crates[prev["crate_key"]]
            del crate_targets[prev["crate_key"]]
            winners[crate] = keep
            crates[keep["crate_key"]] = {
                "crate_key": keep["crate_key"],
                "crate": crate,
                "version": keep["version"],
                "depth": keep["depth"],
                "source": keep["source"],
                "active_features": keep["features"],
            }
            crate_targets[keep["crate_key"]] = target_triple
        return winners[crate]["crate_key"]

    def walk(parent_key: str, parent_depth: int) -> None:
        nonlocal edges_traversed, frames_rejected, truncated_tail
        child_depth = parent_depth + 1
        for edge in edges_by_parent.get(parent_key, []):
            if edge["child"] in exclusions:
                frames_rejected += 1
                continue
            if edge.get("optional") and edge["child"] not in declared:
                frames_rejected += 1
                continue
            if child_depth > cap:
                truncated_tail += 1
                continue
            ver = pins.get(edge["child"], edge["version"])
            from_pin = edge["child"] in pins
            feats = _edge_features(edge, ws_features, aliases)
            src = _source_label(edge["child"], declared, members, from_pin)
            ck = register(
                edge["child"],
                ver,
                child_depth,
                parent_key,
                src,
                feats,
                edge.get("target_triple", "any"),
            )
            edges_traversed += 1
            walk(ck, child_depth)

    for decl in scenario.get("declared", []):
        crate = decl["crate"]
        ver = pins.get(crate, decl["version"])
        from_pin = crate in pins
        feats = _expand_aliases(_sort_features(decl.get("features") or []), aliases)
        if decl.get("default_features"):
            for e in edges:
                if e["parent"] == "root" and e["child"] == crate:
                    feats = _union_features(feats, e.get("default_crate_features") or [])
        if crate in ws_features:
            feats = _union_features(feats, ws_features[crate])
        src = _source_label(crate, declared, members, from_pin)
        ck = register(crate, ver, 1, "root", src, feats, "any")
        walk(ck, 1)

    if not scenario.get("declared"):
        walk("root", 0)

    for key, c in conflicts.items():
        if c["crate"] in pins:
            c["resolution_reason"] = "workspace"
        elif c["resolution_reason"] != "unified":
            c["resolution_reason"] = "nearest"

    resolved = sorted(crates.values(), key=lambda x: x["crate_key"])
    profile = scenario.get("build_profile", "dev")
    profile_mode = scenario.get("profile_mode", "target")
    tags_map = scenario.get("feature_tags") or {}
    runtime_set: list[str] = []
    for c in resolved:
        target = crate_targets.get(c["crate_key"], "any")
        if not _crate_on_runtime_set(c["crate_key"], target, profile_mode):
            continue
        tags = tags_map.get(c["crate"], {})
        filtered = _filter_runtime_features(c["active_features"], profile, tags)
        if profile == "release" and not filtered and c["active_features"]:
            dev = set(tags.get("dev_only_features") or [])
            if all(f in dev for f in c["active_features"]):
                continue
        if filtered or profile != "release":
            runtime_set.append(c["crate_key"])
    runtime_set = sorted(runtime_set)

    conflict_list = sorted(
        conflicts.values(),
        key=lambda x: (x["crate"], x["selected_version"]),
    )
    status = "CONFLICT" if conflict_list else "CLEAN"
    payload_len = _scenario_payload_len(scenario["scenario_id"])
    return {
        "scenario_id": scenario["scenario_id"],
        "status": status,
        "duplicate_edges_skipped": 0,
        "frames_rejected": frames_rejected,
        "truncated_tail": truncated_tail,
        "edges_traversed": edges_traversed,
        "conflict_rejection_count": sum(len(c["rejected_versions"]) for c in conflict_list),
        "conflict_rows_purged": conflict_rows_purged,
        "scenario_payload_digest": _scenario_payload_digest(scenario["scenario_id"]),
        "scenario_payload_crc32": _scenario_payload_crc32(scenario["scenario_id"]),
        "scenario_payload_len": payload_len,
        "scenario_payload_plus": payload_len + frames_rejected + truncated_tail,
        "partial_feature_literals": sum(
            1
            for c in resolved
            for f in c["active_features"]
            if f.startswith("feat:")
        ),
        "wire_reserved": 0,
        "resolved_crates": resolved,
        "runtime_feature_set": runtime_set,
        "feature_conflicts": conflict_list,
    }


def _scenario_payload_digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _scenario_payload_crc32_bytes(raw: bytes) -> str:
    return format(binascii.crc32(raw) & 0xFFFFFFFF, "08x")


def _schema_key_sets() -> tuple[set[str], set[str], set[str], set[str]]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return (
        set(schema["root_keys"]),
        set(schema["scenario_row_keys"]),
        set(schema["resolved_crate_fields"]),
        set(schema["conflict_fields"]),
    )


def _analyze_scenario_obj(
    scenario: dict[str, Any], scenario_raw: bytes | None = None
) -> dict[str, Any]:
    filtered, dup_skipped = _filter_edges(scenario.get("edges") or [])
    pins = dict(scenario.get("workspace_pins") or {})
    declared = {d["crate"]: d for d in scenario.get("declared") or []}
    members = set(scenario.get("workspace_members") or [])
    exclusions = set(scenario.get("exclusions") or [])
    ws_features = scenario.get("workspace_features") or {}
    aliases = scenario.get("feature_aliases") or {}
    out = _resolve_graph(
        scenario, filtered, pins, ws_features, declared, members, exclusions, aliases
    )
    out["duplicate_edges_skipped"] = dup_skipped
    sid = scenario["scenario_id"]
    if scenario_raw is None:
        scenario_raw = (CAPTURES_DIR / f"{sid}.json").read_bytes()
    payload_len = len(scenario_raw)
    out["scenario_payload_digest"] = _scenario_payload_digest_bytes(scenario_raw)
    out["scenario_payload_crc32"] = _scenario_payload_crc32_bytes(scenario_raw)
    out["scenario_payload_len"] = payload_len
    out["scenario_payload_plus"] = (
        payload_len
        + dup_skipped
        + out["frames_rejected"]
        + out["truncated_tail"]
    )
    return out


def _analyze_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    return _analyze_scenario_obj(scenario)


def _expected_row(sid: str) -> dict[str, Any]:
    sc = json.loads((CAPTURES_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    sc["scenario_id"] = sid
    return _analyze_scenario_obj(sc)


def _perturb_scenario_01() -> bool:
    try:
        path = CAPTURES_DIR / "scenario_01.json"
        obj = json.loads(path.read_text(encoding="utf-8"))
        shutil.copy(path, VERIFIER_DIR / "scenario_01_clean.json")
        updated = False
        for decl in obj.get("declared", []):
            if decl.get("crate") == "svc" and decl.get("version") == "0.1.0":
                decl["version"] = "0.2.0"
                updated = True
                break
        if not updated:
            return False
        for edge in obj.get("edges", []):
            if edge.get("parent") == "svc:0.1.0":
                edge["parent"] = "svc:0.2.0"
        perturbed = json.dumps(obj, indent=2) + "\n"
        path.write_text(perturbed, encoding="utf-8")
        (VERIFIER_DIR / "scenario_01_perturbed.json").write_text(perturbed, encoding="utf-8")
        (VERIFIER_DIR / "perturb_marker.txt").write_text("scenario_01.json\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _restore_scenario_01() -> None:
    clean = VERIFIER_DIR / "scenario_01_clean.json"
    if clean.is_file():
        shutil.copy(clean, CAPTURES_DIR / "scenario_01.json")


def _run_make(target: str, log_name: str) -> bool:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["make", target],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    (VERIFIER_DIR / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return proc.returncode == 0


@pytest.fixture(scope="session", autouse=True)
def _verifier_grading_setup() -> None:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("perturb_marker.txt", "report_first.json", "report_perturbed.json"):
        (VERIFIER_DIR / name).unlink(missing_ok=True)
    for path in VERIFIER_DIR.glob("*_clean.json"):
        path.unlink()
    for path in VERIFIER_DIR.glob("scenario_01_perturbed.json"):
        path.unlink()
    for path in VERIFIER_DIR.glob("*.log"):
        path.unlink()

    perturbed = _perturb_scenario_01()
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("build", "build.log")
    _run_make("run", "run.log")
    if perturbed and REPORT_PATH.is_file():
        shutil.copy(REPORT_PATH, REPORT_PERTURBED)
        shutil.copy(REPORT_PATH, REPORT_FIRST)
        _run_make("run", "run2.log")

    _restore_scenario_01()
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("run", "run_restore.log")
    if REPORT_PATH.is_file():
        shutil.copy(REPORT_PATH, REPORT_FIRST)
        _run_make("run", "run_restore2.log")


@pytest.fixture(scope="session", autouse=True)
def _capture_immutable_hashes(_verifier_grading_setup: None) -> None:
    if IMMUTABLE_SHA256:
        return
    for rel in ("Makefile", "go.mod"):
        IMMUTABLE_SHA256[rel] = _sha256_file(APP_DIR / rel)
    for subdir in ("feature-policy", "crate-captures", "preflight-gates"):
        for path in sorted((APP_DIR / subdir).rglob("*")):
            if path.is_file():
                rel = path.relative_to(APP_DIR).as_posix()
                IMMUTABLE_SHA256[rel] = _sha256_file(path)


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH}"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _row(report: dict[str, Any], sid: str) -> dict[str, Any]:
    for row in report["scenarios"]:
        if row["scenario_id"] == sid:
            return row
    raise KeyError(sid)


def test_solution_contract_integrity(report: dict[str, Any]) -> None:
    """Immutable paths, manifest order, exact schema keys, and wire_reserved."""
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        if rel.startswith(("featurectl/", "cargograph/", "build/", "work-captures/")):
            continue
        assert rel in IMMUTABLE_SHA256, f"untracked path {rel}"
        assert _sha256_file(path) == IMMUTABLE_SHA256[rel], f"modified {rel}"

    expected_ids = [
        f"scenario_{i:02d}" for i in range(1, 23)
    ] + ["scenario_24"]
    assert [r["scenario_id"] for r in report["scenarios"]] == expected_ids
    assert report["format_version"] == 3

    root_keys, row_keys, crate_keys, conflict_keys = _schema_key_sets()
    assert set(report.keys()) == root_keys

    for row in report["scenarios"]:
        assert set(row.keys()) == row_keys
        assert row["wire_reserved"] == 0
        assert row["status"] in ("CLEAN", "CONFLICT")
        if row["feature_conflicts"]:
            assert row["status"] == "CONFLICT"
        else:
            assert row["status"] == "CLEAN"
        for crate in row["resolved_crates"]:
            assert set(crate.keys()) == crate_keys
        for conflict in row["feature_conflicts"]:
            assert set(conflict.keys()) == conflict_keys


def test_verifier_perturbed_scenario_01_matches_reference() -> None:
    """Verifier-mutated scenario_01 must replay through the repaired reconciler."""
    marker = VERIFIER_DIR / "perturb_marker.txt"
    perturbed_capture = VERIFIER_DIR / "scenario_01_perturbed.json"
    assert marker.is_file(), "verifier perturb marker missing"
    assert perturbed_capture.is_file(), "verifier perturbed capture missing"
    assert REPORT_PERTURBED.is_file(), "verifier perturbed report missing"

    perturbed_report = json.loads(REPORT_PERTURBED.read_text(encoding="utf-8"))
    perturbed_raw = perturbed_capture.read_bytes()
    scenario = json.loads(perturbed_raw.decode("utf-8"))
    scenario["scenario_id"] = "scenario_01"
    expected = _analyze_scenario_obj(scenario, perturbed_raw)
    got = next(
        row for row in perturbed_report["scenarios"] if row["scenario_id"] == "scenario_01"
    )
    assert got == expected


def test_release_strips_dev_only_from_runtime_not_resolved(
    report: dict[str, Any],
) -> None:
    """Release profile removes dev_only features only from runtime_feature_set."""
    row = _row(report, "scenario_02")
    crate = next(c for c in row["resolved_crates"] if c["crate"] == "serde_json")
    assert "dev_unstable" in crate["active_features"]
    assert "json" in crate["active_features"]
    assert "serde_json:1.0.0" in row["runtime_feature_set"]


def test_workspace_declared_source_label(report: dict[str, Any]) -> None:
    """Workspace members in declared must emit source workspace_declared."""
    row = _row(report, "scenario_03")
    svc = next(c for c in row["resolved_crates"] if c["crate"] == "svc")
    assert svc["source"] == "workspace_declared"
    assert svc["version"] == "0.2.5"


def test_optional_weak_dep_not_traversed(report: dict[str, Any]) -> None:
    """Transitive optional edges are skipped unless the child is declared."""
    row = _row(report, "scenario_04")
    assert not any(c["crate"] == "optional_dep" for c in row["resolved_crates"])
    assert row["frames_rejected"] >= 1


def test_declared_optional_subtree_still_walked(report: dict[str, Any]) -> None:
    """Declared optional crates still traverse their dependency subtrees."""
    row = _row(report, "scenario_05")
    assert any(c["crate"] == "helper" for c in row["resolved_crates"])


def test_shallow_depth_wins_over_deep_transitive(report: dict[str, Any]) -> None:
    """Nearest-wins prefers the shallowest depth for the same crate coordinate."""
    row = _row(report, "scenario_06")
    foo = next(c for c in row["resolved_crates"] if c["crate"] == "foo")
    assert foo["version"] == "1.0.0"
    assert foo["depth"] == 1


def test_parent_key_tiebreak_same_depth(report: dict[str, Any]) -> None:
    """At equal depth the lexicographically smaller parent node key wins."""
    row = _row(report, "scenario_07")
    shared = next(c for c in row["resolved_crates"] if c["crate"] == "shared")
    assert shared["version"] == "1.0.0"


def test_duplicate_edge_id_first_seen_wins(report: dict[str, Any]) -> None:
    """Duplicate edge_id rows are skipped after the first occurrence."""
    row = _row(report, "scenario_08")
    dup = next(c for c in row["resolved_crates"] if c["crate"] == "dup")
    assert dup["version"] == "1.0.0"
    assert row["duplicate_edges_skipped"] == 1


def test_exclusion_blocks_transitive_subtree(report: dict[str, Any]) -> None:
    """Excluded crate coordinates block their entire subtrees."""
    row = _row(report, "scenario_09")
    assert not any(c["crate"] == "leak" for c in row["resolved_crates"])
    assert row["frames_rejected"] >= 1


def test_conflict_rows_purged_on_winner_replacement(report: dict[str, Any]) -> None:
    """Winner replacement purges every stale conflict row for the crate coordinate."""
    row = _row(report, "scenario_10")
    expected = _expected_row("scenario_10")
    purge = next(c for c in row["resolved_crates"] if c["crate"] == "purge")
    assert purge["version"] == "1.0.0"
    assert row["conflict_rows_purged"] == expected["conflict_rows_purged"]
    assert row["conflict_rows_purged"] >= 1
    conf = [c for c in row["feature_conflicts"] if c["crate"] == "purge"]
    assert len(conf) == 1
    assert conf[0]["selected_version"] == "1.0.0"
    assert "3.0.0" in conf[0]["rejected_versions"]


def test_host_profile_mode_filters_target_triple(report: dict[str, Any]) -> None:
    """Host profile_mode keeps only host and any target triple crates on runtime set."""
    row = _row(report, "scenario_11")
    keys = set(row["runtime_feature_set"])
    assert "host_only:1.0.0" in keys
    assert "target_only:1.0.0" not in keys


def test_workspace_pin_and_features_merge(report: dict[str, Any]) -> None:
    """Workspace pins override edge versions and merge workspace feature lists."""
    row = _row(report, "scenario_12")
    pinned = next(c for c in row["resolved_crates"] if c["crate"] == "pinned")
    assert pinned["version"] == "3.0.0"
    assert "ws_feat" in pinned["active_features"]
    assert "from_workspace" in pinned["active_features"]


def test_traversal_depth_cap_truncates_tail(report: dict[str, Any]) -> None:
    """Traversal stops when depth exceeds traversal_depth_cap."""
    row = _row(report, "scenario_13")
    assert row["truncated_tail"] >= 1
    assert not any(c["crate"] == "c" for c in row["resolved_crates"])


def test_partial_feature_literals_counted(report: dict[str, Any]) -> None:
    """Unresolved feat: tokens in active_features increment partial_feature_literals."""
    row = _row(report, "scenario_14")
    assert row["partial_feature_literals"] >= 1


def test_hard_conflict_major_version_severity(report: dict[str, Any]) -> None:
    """Major version rejections produce hard conflict severity."""
    row = _row(report, "scenario_15")
    assert row["status"] == "CONFLICT"
    hard = [c for c in row["feature_conflicts"] if c["severity"] == "hard"]
    assert hard


def test_combined_release_host_workspace_dev_strip(report: dict[str, Any]) -> None:
    """Combined release profile, host mode, and workspace_declared interact correctly."""
    row = _row(report, "scenario_16")
    svc = next(c for c in row["resolved_crates"] if c["crate"] == "svc")
    assert svc["source"] == "workspace_declared"
    assert "dev_hook" in svc["active_features"]
    assert "svc:0.1.0" in row["runtime_feature_set"]


def test_default_features_merge_on_edge(report: dict[str, Any]) -> None:
    """default_features on an edge unions default_crate_features into active_features."""
    row = _row(report, "scenario_17")
    child = next(c for c in row["resolved_crates"] if c["crate"] == "child")
    assert "std" in child["active_features"]


def test_capture_digest_and_chain_tail(report: dict[str, Any]) -> None:
    """Root capture_digest and capture_chain_tail match bundled capture bytes."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    digest = _capture_digest(manifest["scenarios"])
    assert report["capture_digest"] == digest
    assert report["capture_chain_tail"] == _capture_chain_tail(
        manifest["scenarios"], digest
    )


def test_bundled_payload_len_and_le_fields(report: dict[str, Any]) -> None:
    """Bundled and manifest payload length fields match capture file sizes."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    scenarios = manifest["scenarios"]
    assert report["manifest_payload_len"] == _manifest_payload_len()
    assert report["bundled_payload_len"] == _bundled_payload_len(scenarios)
    assert report["manifest_payload_len_le"] == _payload_len_le(report["manifest_payload_len"])
    assert report["bundled_payload_len_le"] == _payload_len_le(report["bundled_payload_len"])


def test_combined_v20_workspace_pin_nearest_purge_release(report: dict[str, Any]) -> None:
    """Complex workspace pin, nearest-wins, release strip, and conflict purge scenario."""
    row = _row(report, "scenario_20")
    core = next(c for c in row["resolved_crates"] if c["crate"] == "core")
    assert core["version"] == "5.0.0"
    assert "runtime" in core["active_features"]
    assert "bench" in core["active_features"]
    assert "core:5.0.0" in row["runtime_feature_set"]


def test_edit_scope_allowlist_enforced() -> None:
    """Only featurectl, cargograph, and build outputs may differ from image hashes."""
    allowed_prefixes = ("featurectl/", "cargograph/", "build/")
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        if rel.startswith(allowed_prefixes):
            continue
        if rel in IMMUTABLE_SHA256:
            assert _sha256_file(path) == IMMUTABLE_SHA256[rel], f"tampered {rel}"


def test_make_build_outputs_only_under_build_dir() -> None:
    """Compiled binaries must live under /app/build only."""
    build_dir = APP_DIR / "build"
    assert (build_dir / "featrecon").is_file()
    for path in APP_DIR.rglob("featrecon"):
        assert path.resolve().is_relative_to(build_dir.resolve())


def test_capture_guard_readonly() -> None:
    """Bundled capture guard file must remain unchanged from the image hash."""
    guard = CAPTURES_DIR / ".capture_guard"
    assert guard.is_file()
    rel = "crate-captures/.capture_guard"
    assert rel in IMMUTABLE_SHA256
    assert _sha256_file(guard) == IMMUTABLE_SHA256[rel]


def test_dev_profile_includes_empty_feature_crates(report: dict[str, Any]) -> None:
    """Dev profile keeps target-passing crates on runtime_feature_set with empty features."""
    row = _row(report, "scenario_04")
    expected = _expected_row("scenario_04")
    assert "app:1.0.0" in row["runtime_feature_set"]
    assert row["runtime_feature_set"] == expected["runtime_feature_set"]


def test_runtime_feature_set_bare_crate_keys_only(report: dict[str, Any]) -> None:
    """runtime_feature_set entries must be bare crate_key strings without feature suffixes."""
    for row in report["scenarios"]:
        for entry in row["runtime_feature_set"]:
            assert "/" not in entry
            assert ":" in entry
            assert entry.count(":") == 1


def test_active_features_arrays_never_null(report: dict[str, Any]) -> None:
    """resolved_crates active_features must always be JSON arrays, never null."""
    for row in report["scenarios"]:
        for crate in row["resolved_crates"]:
            feats = crate["active_features"]
            assert feats is not None
            assert isinstance(feats, list)


def test_report_byte_identical_on_repeat_run() -> None:
    """Repeated make run on unchanged captures must emit byte-identical JSON."""
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH}"
    assert REPORT_FIRST.is_file(), f"missing {REPORT_FIRST}"
    assert REPORT_PATH.read_bytes() == REPORT_FIRST.read_bytes()


def test_scenario_10_reference_engine_agreement(report: dict[str, Any]) -> None:
    """scenario_10 purge lifecycle must match the policy reference replay."""
    got = _row(report, "scenario_10")
    expected = _expected_row("scenario_10")
    assert got["feature_conflicts"] == expected["feature_conflicts"]
    assert got["conflict_rows_purged"] == expected["conflict_rows_purged"]
    assert got["resolved_crates"] == expected["resolved_crates"]


def test_scenario_20_reference_engine_agreement(report: dict[str, Any]) -> None:
    """scenario_20 combined workspace and release rules must match the reference replay."""
    got = _row(report, "scenario_20")
    expected = _expected_row("scenario_20")
    assert got["runtime_feature_set"] == expected["runtime_feature_set"]
    assert got["resolved_crates"] == expected["resolved_crates"]
    assert got["feature_conflicts"] == expected["feature_conflicts"]


def test_release_all_dev_only_crate_excluded_from_runtime(report: dict[str, Any]) -> None:
    """Release profile drops crates whose surviving features are entirely dev_only."""
    row = _row(report, "scenario_19")
    expected = _expected_row("scenario_19")
    mix = next(c for c in row["resolved_crates"] if c["crate"] == "mix")
    assert "dev_only" in mix["active_features"]
    assert "prod" in mix["active_features"]
    assert row["runtime_feature_set"] == expected["runtime_feature_set"]
    assert "mix:1.0.0" in row["runtime_feature_set"]


def test_json_report_single_trailing_newline(report: dict[str, Any]) -> None:
    """Output JSON must end with exactly one trailing newline and use compact separators."""
    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    text = raw.decode("utf-8")
    assert ": " not in text
    assert ", " not in text


def test_feature_aliases_expand_before_merge(report: dict[str, Any]) -> None:
    """feature_aliases must expand into concrete active_features on declared crates."""
    row = _row(report, "scenario_21")
    expected = _expected_row("scenario_21")
    serde = next(c for c in row["resolved_crates"] if c["crate"] == "serde")
    assert set(serde["active_features"]) == {"alloc", "derive"}
    assert row["resolved_crates"] == expected["resolved_crates"]


def test_walk_order_child_before_edge_id(report: dict[str, Any]) -> None:
    """Sibling edges must be walked child ascending then edge_id ascending."""
    got = _row(report, "scenario_22")
    expected = _expected_row("scenario_22")
    pick = next(c for c in got["resolved_crates"] if c["crate"] == "pick")
    assert pick["version"] == expected["resolved_crates"][
        next(i for i, c in enumerate(expected["resolved_crates"]) if c["crate"] == "pick")
    ]["version"]
    assert got["feature_conflicts"] == expected["feature_conflicts"]
    if expected["feature_conflicts"]:
        assert expected["feature_conflicts"][0]["resolution_reason"] == "unified"


def test_unified_resolution_reason_same_parent_loss(report: dict[str, Any]) -> None:
    """Same depth same parent walk order losses use resolution_reason unified."""
    got = _row(report, "scenario_24")
    expected = _expected_row("scenario_24")
    assert got["feature_conflicts"] == expected["feature_conflicts"]
    conf = got["feature_conflicts"][0]
    assert conf["resolution_reason"] == "unified"
    assert conf["selected_version"] == "1.0.0"
