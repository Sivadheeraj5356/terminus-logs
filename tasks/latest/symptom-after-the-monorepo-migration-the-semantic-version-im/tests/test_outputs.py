"""Verification for semantic version impact simulator (Go graph propagation)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

APP_DIR = Path("/app")
GRAPH_DIR = APP_DIR / "release-graphs"
SPEC_DIR = APP_DIR / "semver-spec"
PROBE_DIR = APP_DIR / "probe-scripts"
REPORT_PATH = APP_DIR / "build" / "impact_report.json"
REPORT_FIRST = Path("/logs/verifier/report_first.json")
VERIFIER_DIR = Path("/logs/verifier")
BUILD_DIR = APP_DIR / "build"
MANIFEST_PATH = GRAPH_DIR / "workspace_manifest.json"
FIXTURES_DIR = Path("/opt/svis-fixtures/grading-overrides")

PROJECT_KEYS = [
    "project_id",
    "status",
    "risk_score",
    "upgrade_order",
    "packages_impacted",
    "constraint_violations",
    "propagation_paths",
    "schedule_conflicts",
]
PACKAGE_KEYS = ["package_name", "bump_type", "blast_radius", "risk_score", "tier"]
STATUSES = frozenset({"SAFE", "RISK", "BLOCKED"})
TIERS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
IMMUTABLE_SHA256: dict[str, str] = {}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_version(raw: str) -> tuple[int, int, int, str] | None:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([^+]+))?(?:\+.+)?$", raw.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""


def _compare_versions(a: tuple[int, int, int, str], b: tuple[int, int, int, str]) -> int:
    for i in range(3):
        if a[i] != b[i]:
            return -1 if a[i] < b[i] else 1
    if a[3] == b[3]:
        return 0
    if a[3] == "":
        return 1
    if b[3] == "":
        return -1
    ap, bp = a[3].split("."), b[3].split(".")
    for i in range(max(len(ap), len(bp))):
        av = ap[i] if i < len(ap) else ""
        bv = bp[i] if i < len(bp) else ""
        if av == bv:
            continue
        if av.isdigit() and bv.isdigit():
            if int(av) != int(bv):
                return -1 if int(av) < int(bv) else 1
        elif av != bv:
            return -1 if av < bv else 1
    return 0


def _bump_type(old: str, new: str) -> str:
    o, n = _parse_version(old), _parse_version(new)
    if not o or not n or _compare_versions(n, o) <= 0:
        return "none"
    if n[0] > o[0]:
        return "major"
    if n[1] > o[1]:
        return "minor"
    return "patch"


def _satisfies(constraint: str, version: str) -> bool:
    constraint = constraint.strip()
    ver = _parse_version(version)
    if not ver:
        return False
    if " - " in constraint:
        lo_s, hi_s = constraint.split(" - ", 1)
        lo, hi = _parse_version(lo_s.strip()), _parse_version(hi_s.strip())
        return bool(lo and hi and _compare_versions(ver, lo) >= 0 and _compare_versions(ver, hi) <= 0)
    if constraint.startswith(">="):
        base = _parse_version(constraint[2:].strip())
        return base is not None and _compare_versions(ver, base) >= 0
    if constraint.startswith("^"):
        base = _parse_version(constraint[1:].strip())
        if not base:
            return False
        if base[0] > 0:
            return _compare_versions(ver, base) >= 0 and ver[0] == base[0]
        return _compare_versions(ver, base) >= 0 and ver[0] == 0 and ver[1] == base[1]
    if constraint.startswith("~"):
        base = _parse_version(constraint[1:].strip())
        if not base:
            return False
        return _compare_versions(ver, base) >= 0 and ver[0] == base[0] and ver[1] == base[1]
    base = _parse_version(constraint)
    return base is not None and _compare_versions(ver, base) == 0


def _project_num(pid: str) -> int:
    try:
        return int(pid.split("_", 1)[1])
    except Exception:
        return 1


def _defaults(n: int) -> dict[str, Any]:
    return {
        "risk_cutoff": 0.55 + (n % 5) * 0.03,
        "blast_threshold": 3 + (n % 4),
        "weights": {
            "constraint_break": 0.30,
            "blast_radius": 0.25,
            "schedule_slip": 0.15,
            "peer_mismatch": 0.15,
            "bump_severity": 0.15,
        },
    }


def _round4(v: float) -> float:
    return round(v, 4)


def _py_float(v: float) -> int | float:
    r = _round4(v)
    return int(r) if r == int(r) else r


def _tier(score: float) -> str:
    if score >= 0.75:
        return "CRITICAL"
    if score >= 0.50:
        return "HIGH"
    if score >= 0.25:
        return "MEDIUM"
    return "LOW"


def _blast_radius(graph: dict[str, Any], provider: str) -> int:
    queue = [e["consumer"] for e in graph.get("edges", []) if e.get("edge_type") != "peer" and e["provider"] == provider]
    seen: set[str] = set()
    affected: set[str] = set()
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        affected.add(cur)
        for e in graph.get("edges", []):
            if e.get("edge_type") == "peer":
                continue
            if e["provider"] == cur and e["consumer"] not in seen:
                queue.append(e["consumer"])
    return len(affected)


def _upgrade_order(graph: dict[str, Any], proposed: list[str]) -> list[str]:
    edges = [e for e in graph.get("edges", []) if e.get("edge_type") != "peer"]
    remaining = set(proposed)
    order: list[str] = []
    while remaining:
        ready = []
        for pkg in sorted(remaining):
            deps = {e["provider"] for e in edges if e["consumer"] == pkg and e["provider"] in remaining}
            if not deps:
                ready.append(pkg)
        if not ready:
            order.extend(sorted(remaining))
            break
        order.append(ready[0])
        remaining.remove(ready[0])
    return order


def _score_project(cfg: dict[str, Any], pid: str) -> dict[str, Any]:
    """Independent propagation_rules replay for exact project row comparison."""
    n = _project_num(pid)
    defaults = _defaults(n)
    weights = dict(defaults["weights"])
    weights.update(cfg.get("weights") or {})
    risk_cutoff = float(cfg.get("risk_cutoff", defaults["risk_cutoff"]))
    blast_threshold = int(cfg.get("blast_threshold", defaults["blast_threshold"]))
    freeze = cfg.get("freeze_date", "2026-06-01")
    graph = cfg["graph"]
    versions = {node["name"]: node["version"] for node in graph["nodes"]}
    proposed_map = {p["package"]: p for p in graph.get("proposed", [])}
    for pkg, p in proposed_map.items():
        versions[pkg] = p["target"]

    violations: list[str] = []
    peer_violations = 0
    peer_edges = 0
    required_edges = 0
    for edge in graph.get("edges", []):
        if edge.get("edge_type") == "peer":
            peer_edges += 1
            if edge["provider"] in proposed_map:
                if not _satisfies(edge["constraint"], proposed_map[edge["provider"]]["target"]):
                    peer_violations += 1
            continue
        if edge.get("required", True):
            required_edges += 1
        resolved = versions.get(edge["provider"], "")
        if not _satisfies(edge["constraint"], resolved) and edge.get("required", True):
            violations.append(f"{edge['consumer']}|{edge['provider']}|{edge['constraint']}|{resolved}")

    schedule_conflicts = []
    for p in graph.get("proposed", []):
        if p.get("release_date", "") > freeze:
            schedule_conflicts.append(f"{p['package']}|{p['release_date']}|{freeze}")

    bump_types: dict[str, str] = {}
    severity_vals: list[float] = []
    blast: dict[str, int] = {}
    max_blast = 0
    for p in graph.get("proposed", []):
        pkg = p["package"]
        old = next((nd["version"] for nd in graph["nodes"] if nd["name"] == pkg), p["target"])
        bt = _bump_type(old, p["target"])
        bump_types[pkg] = bt
        severity_vals.append({"major": 1.0, "minor": 0.5, "patch": 0.1, "none": 0.0}[bt])
        br = _blast_radius(graph, pkg)
        blast[pkg] = br
        max_blast = max(max_blast, br)

    cb = min(1.0, len(violations) / max(1, required_edges))
    bb = min(1.0, max_blast / max(1, blast_threshold))
    sc = min(1.0, len(schedule_conflicts) / max(1, len(graph.get("proposed", []))))
    pc = min(1.0, peer_violations / max(1, peer_edges)) if peer_edges else 0.0
    bs = sum(severity_vals) / len(severity_vals) if severity_vals else 0.0
    wsum = sum(weights.values())
    risk = _round4(
        (cb * weights["constraint_break"]
         + bb * weights["blast_radius"]
         + sc * weights["schedule_slip"]
         + pc * weights["peer_mismatch"]
         + bs * weights["bump_severity"]) / wsum
    )

    status = "SAFE"
    if violations:
        status = "BLOCKED"
    elif risk >= risk_cutoff or schedule_conflicts:
        status = "RISK"

    paths = []
    for v in sorted(violations):
        cons, prov, _, resolved = v.split("|", 3)
        old = next((nd["version"] for nd in graph["nodes"] if nd["name"] == prov), resolved)
        bt = bump_types.get(prov, _bump_type(old, resolved))
        paths.append(f"{cons}->{prov}|{bt}|blocked")

    packages_impacted = []
    for p in graph.get("proposed", []):
        pkg = p["package"]
        br = blast.get(pkg, 0)
        pkg_risk = _round4(risk * (br / max_blast)) if max_blast else _round4(risk)
        packages_impacted.append({
            "package_name": pkg,
            "bump_type": bump_types.get(pkg, "none"),
            "blast_radius": br,
            "risk_score": _py_float(pkg_risk),
            "tier": _tier(pkg_risk),
        })
    packages_impacted.sort(key=lambda r: (-r["blast_radius"], r["package_name"]))

    proposed_names = [p["package"] for p in graph.get("proposed", [])]

    return {
        "project_id": pid,
        "status": status,
        "risk_score": _py_float(risk),
        "upgrade_order": _upgrade_order(graph, proposed_names),
        "packages_impacted": packages_impacted,
        "constraint_violations": sorted(violations),
        "propagation_paths": sorted(paths),
        "schedule_conflicts": sorted(schedule_conflicts),
    }


def _project_row(report: dict[str, Any], project_id: str) -> dict[str, Any]:
    for row in report["projects"]:
        if row["project_id"] == project_id:
            return row
    raise KeyError(project_id)


def _run_make(target: str, log_name: str) -> None:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["make", target], cwd=APP_DIR, capture_output=True, text=True)
    (VERIFIER_DIR / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        pytest.fail(f"make {target} failed; see /logs/verifier/{log_name}")


def _swap_graph_run(pid: str, cfg: dict[str, Any], log_tag: str) -> dict[str, Any]:
    cfg_path = GRAPH_DIR / f"{pid}.json"
    backup = VERIFIER_DIR / f"{pid}_swap_backup.json"
    shutil.copy(cfg_path, backup)
    try:
        cfg_path.write_text(json.dumps(cfg, separators=(",", ":")) + "\n", encoding="utf-8")
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", f"swap_{log_tag}.log")
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        return _project_row(report, pid)
    finally:
        shutil.copy(backup, cfg_path)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", f"restore_{log_tag}.log")


@pytest.fixture(scope="session", autouse=True)
def _apply_grading_fixtures() -> None:
    """Copy grading fixture JSON onto release graphs before build and scoring."""
    if FIXTURES_DIR.is_dir():
        for project_json in sorted(FIXTURES_DIR.glob("project_*.json")):
            shutil.copy2(project_json, GRAPH_DIR / project_json.name)


@pytest.fixture(scope="session", autouse=True)
def _verifier_preflight(_apply_grading_fixtures: None) -> None:
    """Build svis and snapshot first run for byte-identical rerun checks."""
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("build", "build.log")
    _run_make("run", "run.log")
    if not REPORT_PATH.is_file():
        pytest.fail(f"missing report at {REPORT_PATH}")
    shutil.copy(REPORT_PATH, REPORT_FIRST)
    _run_make("run", "run2.log")
    if REPORT_PATH.read_bytes() != REPORT_FIRST.read_bytes():
        pytest.fail("make run not byte-identical across consecutive invocations")


@pytest.fixture(scope="session", autouse=True)
def _capture_immutable_hashes(_verifier_preflight: None) -> None:
    if IMMUTABLE_SHA256:
        return
    for rel in ("Makefile", "go.mod"):
        IMMUTABLE_SHA256[rel] = _sha256_file(APP_DIR / rel)
    for root in (GRAPH_DIR, SPEC_DIR, PROBE_DIR):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                IMMUTABLE_SHA256[path.relative_to(APP_DIR).as_posix()] = _sha256_file(path)


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_report_schema_contract(report: dict[str, Any]) -> None:
    """Schema keys compact JSON immutability absolute build paths."""
    for rel, digest in IMMUTABLE_SHA256.items():
        path = APP_DIR / rel
        assert path.is_file(), rel
        assert _sha256_file(path) == digest, rel

    expected_ids = [f"project_{i:02d}" for i in range(1, 21)]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["projects"] == expected_ids
    assert [row["project_id"] for row in report["projects"]] == expected_ids
    assert len(report["projects"]) == 20

    for row in report["projects"]:
        assert list(row.keys()) == PROJECT_KEYS
        assert row["status"] in STATUSES
        for pkg_row in row["packages_impacted"]:
            assert list(pkg_row.keys()) == PACKAGE_KEYS
            assert pkg_row["tier"] in TIERS

    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n") and b": " not in raw and b", " not in raw
    assert b"null" not in raw
    assert REPORT_FIRST.is_file() and raw == REPORT_FIRST.read_bytes()
    assert str(REPORT_PATH) == "/app/build/impact_report.json"
    build_names = {p.name for p in BUILD_DIR.iterdir()}
    assert build_names == {"svis", "impact_report.json"}


def test_independent_replay_all_projects(report: dict[str, Any]) -> None:
    """Every project row must match independent propagation_rules replay."""
    for row in report["projects"]:
        pid = row["project_id"]
        cfg = json.loads((GRAPH_DIR / f"{pid}.json").read_text(encoding="utf-8"))
        expected = _score_project(cfg, pid)
        assert row["status"] == expected["status"], pid
        assert row["risk_score"] == pytest.approx(expected["risk_score"], rel=0, abs=0.001), pid
        assert row["upgrade_order"] == expected["upgrade_order"], pid
        assert row["constraint_violations"] == expected["constraint_violations"], pid
        assert row["propagation_paths"] == expected["propagation_paths"], pid
        assert row["schedule_conflicts"] == expected["schedule_conflicts"], pid
        assert len(row["packages_impacted"]) == len(expected["packages_impacted"]), pid
        for got, exp in zip(row["packages_impacted"], expected["packages_impacted"], strict=True):
            assert got["package_name"] == exp["package_name"], pid
            assert got["bump_type"] == exp["bump_type"], pid
            assert got["blast_radius"] == exp["blast_radius"], pid
            assert got["risk_score"] == pytest.approx(exp["risk_score"], rel=0, abs=0.001), pid
            assert got["tier"] == exp["tier"], pid


def test_major_caret_break_project_01(report: dict[str, Any]) -> None:
    """project_01 major core-lib bump blocks app-shell and uses lowercase blocked path token."""
    row = _project_row(report, "project_01")
    assert row["status"] == "BLOCKED"
    assert row["constraint_violations"] == ["app-shell|core-lib|^1.0.0|2.0.0"]
    assert row["propagation_paths"] == ["app-shell->core-lib|major|blocked"]
    assert all(p.endswith("|blocked") for p in row["propagation_paths"])


def test_prerelease_ordering_project_02(report: dict[str, Any]) -> None:
    """project_02 alpha to beta prerelease bump stays constraint safe."""
    row = _project_row(report, "project_02")
    assert row["status"] == "SAFE"
    assert row["constraint_violations"] == []


def test_tilde_minor_break_project_03(report: dict[str, Any]) -> None:
    """project_03 minor fmt-lib bump violates tilde constraint on cli-tool."""
    row = _project_row(report, "project_03")
    assert row["status"] == "BLOCKED"
    pkg = next(s for s in row["packages_impacted"] if s["package_name"] == "fmt-lib")
    assert pkg["bump_type"] == "minor"


def test_optional_dep_no_block_project_04(report: dict[str, Any]) -> None:
    """project_04 optional dependency violation does not block status."""
    row = _project_row(report, "project_04")
    assert row["status"] == "SAFE"
    assert row["constraint_violations"] == []


def test_fixture_risk_cutoff_project_05(report: dict[str, Any]) -> None:
    """Grading fixture project_05 lowers risk_cutoff to emit RISK status."""
    row = _project_row(report, "project_05")
    assert row["status"] == "RISK"
    assert row["risk_score"] == pytest.approx(0.1375, abs=0.001)


def test_weight_normalization_project_06(report: dict[str, Any]) -> None:
    """project_06 partial weight override divides risk by merged weight sum."""
    cfg = json.loads((GRAPH_DIR / "project_06.json").read_text(encoding="utf-8"))
    expected = _score_project(cfg, "project_06")
    row = _project_row(report, "project_06")
    assert row["risk_score"] == pytest.approx(expected["risk_score"], rel=0, abs=0.001)


def test_blast_radius_ranking_project_07(report: dict[str, Any]) -> None:
    """project_07 base major bump reaches three downstream consumers."""
    row = _project_row(report, "project_07")
    pkg = row["packages_impacted"][0]
    assert pkg["package_name"] == "base"
    assert pkg["blast_radius"] == 3
    assert row["status"] == "BLOCKED"


def test_fixture_high_cutoff_project_08(report: dict[str, Any]) -> None:
    """Grading fixture project_08 raises risk_cutoff keeping patch bump SAFE."""
    row = _project_row(report, "project_08")
    assert row["status"] == "SAFE"
    assert row["risk_score"] == pytest.approx(0.0983, abs=0.001)


def test_hyphen_range_break_project_09(report: dict[str, Any]) -> None:
    """project_09 bounded hyphen range rejects provider above high bound."""
    row = _project_row(report, "project_09")
    assert row["status"] == "BLOCKED"
    assert "consumer9|bounded|1.0.0 - 2.0.0|2.1.0" in row["constraint_violations"]


def test_fixture_blast_threshold_project_10(report: dict[str, Any]) -> None:
    """Grading fixture project_10 blast_threshold one inflates blast component."""
    row = _project_row(report, "project_10")
    assert row["status"] == "BLOCKED"
    assert row["packages_impacted"][0]["blast_radius"] == 2


def test_peer_mismatch_component_project_11(report: dict[str, Any]) -> None:
    """project_11 peer mismatch raises risk only never BLOCKED or constraint_violations."""
    row = _project_row(report, "project_11")
    assert row["status"] == "SAFE"
    assert row["constraint_violations"] == []
    assert row["propagation_paths"] == []
    assert row["risk_score"] == pytest.approx(0.3, abs=0.001)


def test_fixture_peer_weight_project_12(report: dict[str, Any]) -> None:
    """Grading fixture project_12 peer_mismatch weight dominates risk without BLOCKED status."""
    cfg = json.loads((GRAPH_DIR / "project_12.json").read_text(encoding="utf-8"))
    expected = _score_project(cfg, "project_12")
    row = _project_row(report, "project_12")
    assert row["status"] == "SAFE"
    assert row["constraint_violations"] == []
    assert row["risk_score"] == pytest.approx(expected["risk_score"], rel=0, abs=0.001)


def test_upgrade_order_project_13(report: dict[str, Any]) -> None:
    """project_13 upgrade_order places shared provider before svc-a consumer."""
    row = _project_row(report, "project_13")
    assert row["upgrade_order"].index("shared") < row["upgrade_order"].index("svc-a")


def test_fixture_low_cutoff_project_14(report: dict[str, Any]) -> None:
    """Grading fixture project_14 low risk_cutoff still SAFE on patch lodash."""
    row = _project_row(report, "project_14")
    assert row["status"] == "SAFE"


def test_patch_safe_project_15(report: dict[str, Any]) -> None:
    """project_15 patch bump keeps caret satisfied and status SAFE."""
    row = _project_row(report, "project_15")
    assert row["status"] == "SAFE"
    assert row["packages_impacted"][0]["bump_type"] == "patch"


def test_minor_break_project_16(report: dict[str, Any]) -> None:
    """project_16 esbuild minor bump breaks caret zero-major constraint."""
    row = _project_row(report, "project_16")
    assert row["status"] == "BLOCKED"


def test_schedule_freeze_conflict_project_17(report: dict[str, Any]) -> None:
    """project_17 release after freeze_date yields RISK via schedule_conflicts."""
    row = _project_row(report, "project_17")
    assert row["status"] == "RISK"
    assert row["schedule_conflicts"] == ["late-rel|2026-08-15|2026-06-01"]


def test_fixture_risk_project_18(report: dict[str, Any]) -> None:
    """Grading fixture project_18 risk_cutoff keeps minor axios bump SAFE."""
    row = _project_row(report, "project_18")
    assert row["status"] == "SAFE"


def test_transitive_chain_project_19(report: dict[str, Any]) -> None:
    """project_19 traces dep-x and legacy-b from core-a major propagation."""
    row = _project_row(report, "project_19")
    assert row["status"] == "BLOCKED"
    pkg = row["packages_impacted"][0]
    assert pkg["blast_radius"] >= 2


def test_fixture_schedule_weight_project_20(report: dict[str, Any]) -> None:
    """Grading fixture project_20 schedule_slip weight yields RISK on late release."""
    row = _project_row(report, "project_20")
    assert row["status"] == "RISK"
    assert row["schedule_conflicts"]


def test_runtime_caret_zero_major_swap() -> None:
    """Runtime swap confirms zero-major caret allows only matching minor line."""
    cfg = json.loads((GRAPH_DIR / "project_01.json").read_text(encoding="utf-8"))
    cfg["graph"]["nodes"] = [
        {"name": "core-lib", "version": "0.8.5"},
        {"name": "app-shell", "version": "1.0.0"},
    ]
    cfg["graph"]["edges"] = [
        {"consumer": "app-shell", "provider": "core-lib", "constraint": "^0.8.0", "required": True},
    ]
    cfg["graph"]["proposed"] = [{"package": "core-lib", "target": "0.9.0", "release_date": "2026-01-01"}]
    row = _swap_graph_run("project_01", cfg, "caret_zero")
    assert row["status"] == "BLOCKED"


def test_runtime_tilde_patch_allowed_swap() -> None:
    """Runtime swap confirms tilde range accepts patch level bump only."""
    cfg = json.loads((GRAPH_DIR / "project_03.json").read_text(encoding="utf-8"))
    cfg["graph"]["proposed"] = [{"package": "fmt-lib", "target": "1.2.4", "release_date": "2026-01-01"}]
    row = _swap_graph_run("project_03", cfg, "tilde_patch")
    assert row["status"] == "SAFE"


def test_main_absolute_path_contract() -> None:
    """impact-engine main must use absolute graph paths and forbid shell exec patterns."""
    src = (APP_DIR / "impact-engine/main.go").read_text(encoding="utf-8")
    for needle in (
        "/app/release-graphs",
        "workspace_manifest.json",
        "/app/build/impact_report.json",
    ):
        assert needle in src
    for forbidden in ("os/exec", "bash -c", ";curl", ";wget", ";bash", ";sh"):
        assert forbidden not in src


def test_edit_scope_immutable_bundle_tree() -> None:
    """Agent edits must not modify Makefile go.mod graphs spec or probe scripts."""
    for rel, digest in IMMUTABLE_SHA256.items():
        assert _sha256_file(APP_DIR / rel) == digest, rel


def test_report_raw_json_key_order_contract(report: dict[str, Any]) -> None:
    """Raw JSON must preserve project and package key order from report_schema."""
    raw = REPORT_PATH.read_text(encoding="utf-8")
    assert raw.index('"project_id"') < raw.index('"status"') < raw.index('"risk_score"')
    assert '"package_name"' in raw and raw.index('"package_name"') < raw.index('"bump_type"')
