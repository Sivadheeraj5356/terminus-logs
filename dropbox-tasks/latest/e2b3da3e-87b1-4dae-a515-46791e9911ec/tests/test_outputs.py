"""Verifier for lockctl nonlinear canal transient simulator (schema version 4)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

ENV = Path("/app/environment")
BIN = ENV / "build" / "lockctl"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001

SOLVER = {
    "initial_step_s": 30.0,
    "minimum_step_s": 0.46875,
    "maximum_step_s": 120.0,
    "volume_abs_tolerance_m3": 1e-7,
    "volume_rel_tolerance": 1e-8,
    "newton_abs_tolerance_m3": 1e-9,
    "newton_rel_tolerance": 1e-10,
    "maximum_newton_iterations": 12,
}


def _strip_setid_under_app() -> None:
    """Remove setuid/setgid bits from agent-controlled files under /app."""
    for root, _dirs, files in os.walk("/app"):
        for name in files:
            path = Path(root) / name
            try:
                mode = path.stat().st_mode
            except OSError:
                continue
            if mode & (stat.S_ISUID | stat.S_ISGID):
                path.chmod(mode & ~(stat.S_ISUID | stat.S_ISGID))


def _normalize_binary() -> None:
    """Ensure the rebuilt binary has no setuid/setgid bits and is world-executable."""
    if not BIN.exists():
        return
    mode = BIN.stat().st_mode
    BIN.chmod((mode | 0o755) & ~(stat.S_ISUID | stat.S_ISGID))


def rebuild() -> None:
    """Rebuild the release binary from current environment sources."""
    subprocess.run(
        ["cmake", "-S", str(ENV), "-B", str(ENV / "build")],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["cmake", "--build", str(ENV / "build"), "--target", "lockctl", "-j2"],
        check=True,
        capture_output=True,
        text=True,
    )
    _normalize_binary()
    _strip_setid_under_app()


@pytest.fixture(scope="session", autouse=True)
def _built_binary() -> None:
    """Ensure lockctl exists before tests run."""
    rebuild()
    assert BIN.exists()


def _candidate_writable(path: Path) -> None:
    """Allow the unprivileged candidate to write into a working directory."""
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o777)


@pytest.fixture
def work_path() -> Path:
    """World-traversable workdir (pytest tmp_path parents are 0700 and block UID 10001)."""
    root = Path("/tmp") / f"lockctl-cand-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    os.chmod(root, 0o777)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def run_lockctl(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Invoke lockctl under the dedicated unprivileged identity."""
    _normalize_binary()
    _strip_setid_under_app()
    cmd = [
        "setpriv",
        f"--reuid={CANDIDATE_UID}",
        f"--regid={CANDIDATE_GID}",
        "--clear-groups",
        "--nnp",
        "--",
        str(BIN),
        *args,
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    err = (proc.stderr or "") + (proc.stdout or "")
    if proc.returncode != 0 and (
        "No such file or directory" in err
        or "cannot find" in err.lower()
        or "failed to execute" in err.lower()
        or "setpriv:" in err
        or proc.returncode in (126, 127)
    ):
        # Host/dev fallback when the dedicated candidate identity is unavailable.
        proc = subprocess.run([str(BIN), *args], check=False, capture_output=True, text=True)
        cmd = [str(BIN), *args]
    if check and proc.returncode != 0:
        raise AssertionError(
            f"lockctl failed rc={proc.returncode}\ncmd={cmd}\nstderr={proc.stderr}\nstdout={proc.stdout}"
        )
    return proc


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=True) + "\n")
    os.chmod(path, 0o644)


def _noop_forcing(path: Path, link_id: str | None = None, node_id: str | None = None) -> None:
    """Write a one-line JSONL forcing file that does not change hydraulics."""
    if link_id is not None:
        event = {
            "event_id": "noop",
            "source_seq": 1,
            "time_s": 0,
            "event_type": "link_control",
            "link_id": link_id,
            "control": 1.0,
        }
    else:
        assert node_id is not None
        event = {
            "event_id": "noop",
            "source_seq": 1,
            "time_s": 0,
            "event_type": "external_inflow",
            "node_id": node_id,
            "flow_m3_s": 0.0,
        }
    path.write_text(json.dumps(event, separators=(",", ":")) + "\n")
    os.chmod(path, 0o644)


def materialize_trusted_demo(tmp_path: Path) -> dict[str, Path]:
    """Copy verifier-owned fixtures into a fresh workspace and rewrite absolute paths."""
    _candidate_writable(tmp_path)
    topo = tmp_path / "topology_demo.json"
    force = tmp_path / "forcing_demo.jsonl"
    phase1 = tmp_path / "forcing_demo_phase1.jsonl"
    phase2 = tmp_path / "forcing_demo_phase2.jsonl"
    case = tmp_path / "case_demo.json"
    shutil.copyfile(FIXTURES / "topology_demo.json", topo)
    shutil.copyfile(FIXTURES / "forcing_demo.jsonl", force)
    shutil.copyfile(FIXTURES / "forcing_demo_phase1.jsonl", phase1)
    shutil.copyfile(FIXTURES / "forcing_demo_phase2.jsonl", phase2)
    case_obj = json.loads((FIXTURES / "case_demo.json").read_text())
    case_obj["topology_path"] = str(topo.resolve())
    case_obj["forcing_path"] = str(force.resolve())
    _write_json(case, case_obj)
    for p in (topo, force, phase1, phase2, case):
        os.chmod(p, 0o644)
    out_dir = tmp_path / "output"
    _candidate_writable(out_dir)
    return {
        "case": case,
        "topo": topo,
        "force": force,
        "phase1": phase1,
        "phase2": phase2,
        "out_dir": out_dir,
    }


@pytest.fixture
def demo(work_path: Path) -> dict[str, Path]:
    """Per-test trusted demo materialization."""
    return materialize_trusted_demo(work_path)


def run_case_to_report(
    work_path: Path,
    topology: dict[str, Any],
    *,
    stop_at: int = 0,
    end_time_s: int = 0,
    output_interval_s: int = 600,
    link_id: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Write topology/forcing/case, invoke lockctl run, and return the report JSON."""
    _candidate_writable(work_path)
    topo_path = work_path / "topology.json"
    force_path = work_path / "forcing.jsonl"
    case_path = work_path / "case.json"
    out_path = work_path / "report.json"
    _write_json(topo_path, topology)
    _noop_forcing(force_path, link_id=link_id, node_id=node_id)
    case = {
        "schema_version": 4,
        "case_id": "constitutive-probe",
        "start_time_s": 0,
        "end_time_s": end_time_s,
        "output_interval_s": output_interval_s,
        "topology_path": str(topo_path.resolve()),
        "forcing_path": str(force_path.resolve()),
        "solver": SOLVER,
    }
    _write_json(case_path, case)
    proc = run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--stop-at",
            str(stop_at),
            "--output",
            str(out_path.resolve()),
        ],
        check=False,
    )
    assert proc.returncode == 0, f"lockctl failed:\n{proc.stderr}\n{proc.stdout}"
    return json.loads(out_path.read_text())


def _node_by_id(sample: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in sample["nodes"]:
        if node["node_id"] == node_id:
            return node
    raise AssertionError(f"node {node_id} missing from sample")


def _link_by_id(sample: dict[str, Any], link_id: str) -> dict[str, Any]:
    for link in sample["links"]:
        if link["link_id"] == link_id:
            return link
    raise AssertionError(f"link {link_id} missing from sample")


def _is_hex64(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def independent_report_audit_digest(report_text: str) -> str:
    """SHA-256 of on-disk report bytes with the trailing audit_digest_hex field stripped."""
    raw = report_text[:-1] if report_text.endswith("\n") else report_text
    marker = ',"audit_digest_hex":'
    pos = raw.rfind(marker)
    assert pos != -1, "audit_digest_hex field missing from report"
    material = raw[:pos] + "}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def independent_snapshot_digest(snapshot_text: str) -> str:
    """SHA-256 of on-disk snapshot bytes with the trailing snapshot_digest_hex field stripped."""
    raw = snapshot_text[:-1] if snapshot_text.endswith("\n") else snapshot_text
    marker = ',"snapshot_digest_hex":'
    pos = raw.rfind(marker)
    assert pos != -1, "snapshot_digest_hex field missing from snapshot"
    material = raw[:pos] + "}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def assert_report_audit_digest(report_path: Path) -> None:
    text = report_path.read_text()
    report = json.loads(text)
    digest = report["audit_digest_hex"]
    assert _is_hex64(digest)
    assert digest == independent_report_audit_digest(text)


def assert_snapshot_digest(snapshot_path: Path) -> None:
    text = snapshot_path.read_text()
    snap = json.loads(text)
    digest = snap["snapshot_digest_hex"]
    assert _is_hex64(digest)
    assert digest == independent_snapshot_digest(text)


def test_binary_exists_after_rebuild() -> None:
    """Release binary must exist after a clean CMake rebuild."""
    assert BIN.is_file()


def test_help_mentions_commands() -> None:
    """CLI help must mention run, restore, audit, and key flags."""
    proc = run_lockctl(["--help"])
    text = proc.stdout + proc.stderr
    for token in ["run", "restore", "audit", "--case", "--output", "--snapshot", "--stop-at", "--ledger"]:
        assert token in text


def test_absolute_path_required(work_path: Path) -> None:
    """Relative --case paths must fail."""
    out = work_path / "x.json"
    proc = run_lockctl(["run", "--case", "case.json", "--output", str(out)], check=False)
    assert proc.returncode != 0


def test_bundled_demo_produces_schema_v4(demo: dict[str, Path]) -> None:
    """Bundled demo case must emit a schema-version-4 completed report."""
    out = demo["out_dir"] / "transient_report.json"
    if out.exists():
        out.unlink()
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    report = json.loads(out.read_text())
    assert report["schema_version"] == 4
    assert report["completed"] is True
    assert report["simulated_until_s"] == 3600
    assert isinstance(report["samples"], list) and len(report["samples"]) >= 2
    assert "diagnostics" in report
    assert_report_audit_digest(out)


def test_sample_node_and_link_ordering(demo: dict[str, Path]) -> None:
    """Each sample must list nodes and links in ascending ID order."""
    out = demo["out_dir"] / "ordering_report.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    report = json.loads(out.read_text())
    for sample in report["samples"]:
        node_ids = [n["node_id"] for n in sample["nodes"]]
        link_ids = [link["link_id"] for link in sample["links"]]
        assert node_ids == sorted(node_ids)
        assert link_ids == sorted(link_ids)


def test_binary_multiknot_storage_reports_correct_level_and_volume(work_path: Path) -> None:
    """Compiled storage inverse must use all knots, not only the first segment."""
    topology = {
        "schema_version": 4,
        "gravity_m_s2": 9.80665,
        "nodes": [
            {
                "node_id": "pool",
                "node_type": "storage",
                "initial_level_m": 2.0,
                "storage_curve_revision": 1,
                "storage_curve": [
                    {"level_m": 0.0, "volume_m3": 0.0},
                    {"level_m": 1.0, "volume_m3": 100.0},
                    {"level_m": 3.0, "volume_m3": 500.0},
                ],
            }
        ],
        "links": [],
        "initial_inflows": [{"node_id": "pool", "flow_m3_s": 0.0}],
    }
    report = run_case_to_report(work_path, topology, node_id="pool")
    sample0 = report["samples"][0]
    assert sample0["time_s"] == 0
    node = _node_by_id(sample0, "pool")
    assert node["volume_m3"] == pytest.approx(300.0)
    assert node["level_m"] == pytest.approx(2.0), (
        f"expected level 2.0 from multi-knot inverse, got {node['level_m']}"
    )



def test_binary_gate_flow_reverses_sign_and_matches_law(work_path: Path) -> None:
    """Compiled gate law must reverse with head and match the documented magnitude."""
    topology = {
        "schema_version": 4,
        "gravity_m_s2": 9.80665,
        "nodes": [
            {
                "node_id": "hi",
                "node_type": "storage",
                "initial_level_m": 12.0,
                "storage_curve_revision": 1,
                "storage_curve": [
                    {"level_m": 0.0, "volume_m3": 0.0},
                    {"level_m": 12.0, "volume_m3": 1200.0},
                    {"level_m": 20.0, "volume_m3": 2000.0},
                ],
            },
            {"node_id": "lo", "node_type": "boundary", "initial_level_m": 11.0},
        ],
        "links": [
            {
                "link_id": "gate_hl",
                "link_type": "gate",
                "from_node": "hi",
                "to_node": "lo",
                "discharge_coefficient": 0.5,
                "area_m2": 0.2,
                "initial_control": 1.0,
                "maximum_abs_flow_m3_s": 50.0,
            },
            {
                "link_id": "gate_lh",
                "link_type": "gate",
                "from_node": "lo",
                "to_node": "hi",
                "discharge_coefficient": 0.5,
                "area_m2": 0.2,
                "initial_control": 1.0,
                "maximum_abs_flow_m3_s": 50.0,
            },
        ],
        "initial_inflows": [{"node_id": "hi", "flow_m3_s": 0.0}],
    }
    expected_mag = 0.5 * 0.2 * math.sqrt(2.0 * 9.80665 * 1.0)
    report = run_case_to_report(work_path, topology, link_id="gate_hl")
    sample0 = report["samples"][0]
    q_hl = _link_by_id(sample0, "gate_hl")["flow_m3_s"]
    q_lh = _link_by_id(sample0, "gate_lh")["flow_m3_s"]
    # Report floats are round-half-even to 9 places then streamed with default
    # C++ precision; 1e-4 remains far tighter than a missing sign flip.
    tol = 1e-4
    assert q_hl > 0, f"high-to-low gate flow must be positive, got {q_hl}"
    assert q_lh < 0, f"low-to-high gate flow must be negative, got {q_lh}"
    assert q_hl == pytest.approx(expected_mag, abs=tol)
    assert q_lh == pytest.approx(-expected_mag, abs=tol)
    assert q_hl + q_lh == pytest.approx(0.0, abs=tol)


def test_binary_weir_flow_applies_submergence(work_path: Path) -> None:
    """Compiled weir law must reduce discharge under downstream submergence."""
    topology = {
        "schema_version": 4,
        "gravity_m_s2": 9.80665,
        "nodes": [
            {
                "node_id": "up",
                "node_type": "storage",
                "initial_level_m": 13.0,
                "storage_curve_revision": 1,
                "storage_curve": [
                    {"level_m": 0.0, "volume_m3": 0.0},
                    {"level_m": 13.0, "volume_m3": 1300.0},
                    {"level_m": 20.0, "volume_m3": 2000.0},
                ],
            },
            {"node_id": "free_ds", "node_type": "boundary", "initial_level_m": 10.0},
            {"node_id": "sub_ds", "node_type": "boundary", "initial_level_m": 12.5},
        ],
        "links": [
            {
                "link_id": "weir_free",
                "link_type": "weir",
                "from_node": "up",
                "to_node": "free_ds",
                "discharge_coefficient": 1.4,
                "width_m": 2.0,
                "crest_level_m": 11.0,
                "initial_control": 1.0,
                "maximum_abs_flow_m3_s": 50.0,
            },
            {
                "link_id": "weir_sub",
                "link_type": "weir",
                "from_node": "up",
                "to_node": "sub_ds",
                "discharge_coefficient": 1.4,
                "width_m": 2.0,
                "crest_level_m": 11.0,
                "initial_control": 1.0,
                "maximum_abs_flow_m3_s": 50.0,
            },
        ],
        "initial_inflows": [{"node_id": "up", "flow_m3_s": 0.0}],
    }

    def expected_weir(h_from: float, h_to: float) -> float:
        crest = 11.0
        upstream_head = h_from - crest
        ratio = max(0.0, min(1.0, (h_to - crest) / upstream_head))
        factor = (1.0 - ratio) ** 0.385
        return 1.0 * 1.4 * 2.0 * (upstream_head**1.5) * factor

    free_exp = expected_weir(13.0, 10.0)
    sub_exp = expected_weir(13.0, 12.5)
    report = run_case_to_report(work_path, topology, link_id="weir_free")
    sample0 = report["samples"][0]
    free_flow = _link_by_id(sample0, "weir_free")["flow_m3_s"]
    sub_flow = _link_by_id(sample0, "weir_sub")["flow_m3_s"]
    # Serialization-safe tolerance (see gate test); still far below submergence gap.
    tol = 1e-4
    assert free_flow == pytest.approx(free_exp, abs=tol)
    assert sub_flow == pytest.approx(sub_exp, abs=tol)
    assert free_flow > sub_flow > 0, (
        f"submergence must reduce positive weir flow: free={free_flow}, submerged={sub_flow}"
    )


def test_deterministic_repeat(demo: dict[str, Path]) -> None:
    """Repeated identical runs must produce byte-identical reports."""
    out1 = demo["out_dir"] / "rep1.json"
    out2 = demo["out_dir"] / "rep2.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out1)])
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out2)])
    assert out1.read_bytes() == out2.read_bytes()


def test_audit_accepts_fresh_report(demo: dict[str, Path]) -> None:
    """Audit must succeed (exit 0) on a freshly recomputed completed report."""
    out = demo["out_dir"] / "audit_ok.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    proc = run_lockctl(["audit", "--case", str(demo["case"]), "--ledger", str(out)], check=False)
    assert proc.returncode == 0, f"audit should accept fresh report:\n{proc.stderr}\n{proc.stdout}"


def test_audit_rejects_tampered_sample(demo: dict[str, Path], work_path: Path) -> None:
    """Audit must reject (nonzero exit) a report whose scientific values were altered."""
    out = demo["out_dir"] / "audit_base.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    report = json.loads(out.read_text())
    report["samples"][0]["conservation"]["mass_residual_m3"] += 1.0
    tampered = work_path / "tampered.json"
    tampered.write_text(json.dumps(report) + "\n")
    os.chmod(tampered, 0o644)
    proc = run_lockctl(
        ["audit", "--case", str(demo["case"]), "--ledger", str(tampered)],
        check=False,
    )
    assert proc.returncode != 0, "tampered scientific field must fail audit"


def test_partial_stop_and_snapshot(demo: dict[str, Path]) -> None:
    """A --stop-at run must write an incomplete report and optional snapshot."""
    partial = demo["out_dir"] / "partial.json"
    snap = demo["out_dir"] / "snap.json"
    run_lockctl(
        [
            "run",
            "--case",
            str(demo["case"]),
            "--stop-at",
            "1800",
            "--output",
            str(partial),
            "--snapshot-out",
            str(snap),
        ]
    )
    report = json.loads(partial.read_text())
    assert report["completed"] is False
    assert report["simulated_until_s"] == 1800
    assert snap.exists()
    snap_obj = json.loads(snap.read_text())
    assert snap_obj["schema_version"] == 4
    assert "snapshot_digest_hex" in snap_obj
    assert_snapshot_digest(snap)


def test_canonical_report_audit_digest(demo: dict[str, Path]) -> None:
    """Fresh completed report audit_digest_hex must match an independent SHA-256."""
    out = demo["out_dir"] / "digest_report.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    assert_report_audit_digest(out)


def test_canonical_snapshot_digest(demo: dict[str, Path]) -> None:
    """Fresh partial snapshot_digest_hex must match an independent SHA-256."""
    partial = demo["out_dir"] / "digest_partial.json"
    snap = demo["out_dir"] / "digest_snap.json"
    run_lockctl(
        [
            "run",
            "--case",
            str(demo["case"]),
            "--stop-at",
            "1800",
            "--output",
            str(partial),
            "--snapshot-out",
            str(snap),
        ]
    )
    assert_snapshot_digest(snap)


def test_mass_residual_bounded(demo: dict[str, Path]) -> None:
    """Bundled completed run mass residuals must stay below solver-scale tolerance."""
    out = demo["out_dir"] / "mass_report.json"
    run_lockctl(["run", "--case", str(demo["case"]), "--output", str(out)])
    report = json.loads(out.read_text())
    max_res = report["diagnostics"]["maximum_abs_mass_residual_m3"]
    assert max_res < 1e-6, f"diagnostics maximum residual too large: {max_res}"
    for sample in report["samples"]:
        residual = sample["conservation"]["mass_residual_m3"]
        assert abs(residual) < 1e-6, f"sample residual too large: {residual}"


def _demo_case_with_forcing(work_path: Path, demo: dict[str, Path], forcing_path: Path) -> Path:
    """Create a temporary case JSON pointing at trusted topology and a temp forcing path."""
    case = {
        "schema_version": 4,
        "case_id": "north-lock-transient",
        "start_time_s": 0,
        "end_time_s": 3600,
        "output_interval_s": 600,
        "topology_path": str(demo["topo"].resolve()),
        "forcing_path": str(forcing_path.resolve()),
        "solver": SOLVER,
    }
    case_path = work_path / "case_restore.json"
    _write_json(case_path, case)
    return case_path


def test_restore_append_only_forcing_is_byte_identical_to_clean_run(
    work_path: Path, demo: dict[str, Path]
) -> None:
    """Restore over append-only forcing must match a clean full run byte-for-byte."""
    forcing_path = work_path / "forcing.jsonl"
    phase1 = demo["phase1"].read_bytes()
    phase2 = demo["phase2"].read_bytes()
    forcing_path.write_bytes(phase1)
    os.chmod(forcing_path, 0o644)
    case_path = _demo_case_with_forcing(work_path, demo, forcing_path)
    partial = work_path / "partial.json"
    snap = work_path / "snap.json"
    restored = work_path / "restored.json"
    clean = work_path / "clean.json"

    run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--stop-at",
            "1800",
            "--output",
            str(partial.resolve()),
            "--snapshot-out",
            str(snap.resolve()),
        ]
    )
    with forcing_path.open("ab") as handle:
        handle.write(phase2)

    run_lockctl(
        [
            "restore",
            "--case",
            str(case_path.resolve()),
            "--snapshot",
            str(snap.resolve()),
            "--output",
            str(restored.resolve()),
        ]
    )
    run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--output",
            str(clean.resolve()),
        ]
    )
    assert restored.read_bytes() == clean.read_bytes(), (
        "restored report must be byte-identical to a clean run over the same final forcing"
    )


def _restore_with_sentinel(
    work_path: Path,
    demo: dict[str, Path],
    *,
    prepare_forcing,
    prepare_snapshot=None,
) -> tuple[subprocess.CompletedProcess[str], bytes]:
    """Run restore against a prepared invalid continuation; return proc and sentinel bytes."""
    forcing_path = work_path / "forcing.jsonl"
    phase1 = demo["phase1"].read_bytes()
    forcing_path.write_bytes(phase1)
    os.chmod(forcing_path, 0o644)
    case_path = _demo_case_with_forcing(work_path, demo, forcing_path)
    partial = work_path / "partial.json"
    snap = work_path / "snap.json"
    out_path = work_path / "restore_out.json"
    run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--stop-at",
            "1800",
            "--output",
            str(partial.resolve()),
            "--snapshot-out",
            str(snap.resolve()),
        ]
    )
    prepare_forcing(forcing_path, phase1)
    if prepare_snapshot is not None:
        prepare_snapshot(snap)
    sentinel = b"SENTINEL_RESTORE_OUTPUT_UNCHANGED\n"
    out_path.write_bytes(sentinel)
    os.chmod(out_path, 0o666)
    proc = run_lockctl(
        [
            "restore",
            "--case",
            str(case_path.resolve()),
            "--snapshot",
            str(snap.resolve()),
            "--output",
            str(out_path.resolve()),
        ],
        check=False,
    )
    return proc, out_path.read_bytes()


@pytest.mark.parametrize(
    "kind",
    [
        "rewritten_prefix",
        "truncated_forcing",
        "reused_source_seq",
        "stale_event_time",
    ],
)
def test_restore_rejects_invalid_continuations_without_mutating_output(
    work_path: Path, demo: dict[str, Path], kind: str
) -> None:
    """Invalid append-only continuations must fail restore without changing the output file."""

    def prepare(forcing_path: Path, phase1: bytes) -> None:
        if kind == "rewritten_prefix":
            lines = phase1.decode().splitlines(keepends=True)
            lines[0] = lines[0].replace('"flow_m3_s":0.01', '"flow_m3_s":0.02', 1)
            forcing_path.write_bytes("".join(lines).encode() + demo["phase2"].read_bytes())
        elif kind == "truncated_forcing":
            forcing_path.write_bytes(phase1[: max(1, len(phase1) // 2)])
        elif kind == "reused_source_seq":
            forcing_path.write_bytes(
                phase1
                + (
                    json.dumps(
                        {
                            "event_id": "dup_seq",
                            "source_seq": 3,
                            "time_s": 2100,
                            "event_type": "link_control",
                            "link_id": "gate_upper",
                            "control": 0.2,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
        elif kind == "stale_event_time":
            forcing_path.write_bytes(
                phase1
                + (
                    json.dumps(
                        {
                            "event_id": "stale_time",
                            "source_seq": 99,
                            "time_s": 1800,
                            "event_type": "link_control",
                            "link_id": "gate_upper",
                            "control": 0.2,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
        else:
            raise AssertionError(kind)
        os.chmod(forcing_path, 0o644)

    proc, out_bytes = _restore_with_sentinel(work_path, demo, prepare_forcing=prepare)
    assert proc.returncode != 0, f"{kind}: restore should reject invalid continuation"
    assert out_bytes == b"SENTINEL_RESTORE_OUTPUT_UNCHANGED\n", (
        f"{kind}: rejected restore must not mutate the output file"
    )


def test_restore_rejects_corrupt_snapshot_without_mutating_output(
    work_path: Path, demo: dict[str, Path]
) -> None:
    """Tampered snapshot scientific state with a stale digest must not rewrite outputs."""

    def prepare_forcing(forcing_path: Path, phase1: bytes) -> None:
        forcing_path.write_bytes(phase1 + demo["phase2"].read_bytes())
        os.chmod(forcing_path, 0o644)

    def prepare_snapshot(snap: Path) -> None:
        obj = json.loads(snap.read_text())
        obj["storage_state"][0]["volume_m3"] = float(obj["storage_state"][0]["volume_m3"]) + 123.456
        snap.write_text(json.dumps(obj, separators=(",", ":")) + "\n")
        os.chmod(snap, 0o644)

    proc, out_bytes = _restore_with_sentinel(
        work_path, demo, prepare_forcing=prepare_forcing, prepare_snapshot=prepare_snapshot
    )
    assert proc.returncode != 0, "corrupt snapshot digest must fail restore"
    assert out_bytes == b"SENTINEL_RESTORE_OUTPUT_UNCHANGED\n", (
        "rejected corrupt snapshot must not mutate the output file"
    )


def test_candidate_cannot_read_verifier_sources() -> None:
    """Unprivileged candidate identity must not read verifier source paths."""
    target = Path(__file__).resolve()
    proc = subprocess.run(
        [
            "setpriv",
            f"--reuid={CANDIDATE_UID}",
            f"--regid={CANDIDATE_GID}",
            "--clear-groups",
            "--nnp",
            "--",
            "python3",
            "-c",
            f"open({str(target)!r}).read()",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 127:
        pytest.skip("setpriv/candidate user unavailable on host")
    assert proc.returncode != 0


# ---------------------------------------------------------------------------
# Adaptive step-doubling scientific coverage (binary-level)
# ---------------------------------------------------------------------------

_ADAPT_DT = 20.0
_ADAPT_V0 = 500.0
_ADAPT_G = 9.80665
_ADAPT_K = 0.8 * 1.0 * 1.0  # control * Cd * area
_ADAPT_H_SOURCE = 15.0


def _adapt_level_from_volume(volume_m3: float) -> float:
    """Linear storage: V = 100 * level over [0, 20] m."""
    return volume_m3 / 100.0


def _adapt_gate_flow(volume_m3: float) -> float:
    """Independent orifice gate law from source(15) into pool(volume)."""
    delta_h = _ADAPT_H_SOURCE - _adapt_level_from_volume(volume_m3)
    if delta_h == 0.0:
        return 0.0
    sign = 1.0 if delta_h > 0.0 else -1.0
    return _ADAPT_K * sign * math.sqrt(2.0 * _ADAPT_G * abs(delta_h))


def _adapt_implicit_midpoint(v0: float, dt: float) -> float:
    """Scalar implicit midpoint via bisection: V1 - V0 - dt*q((V0+V1)/2)=0."""
    lo, hi = 0.0, 2000.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        residual = mid - v0 - dt * _adapt_gate_flow(0.5 * (v0 + mid))
        if residual > 0.0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _adapt_reference() -> dict[str, float]:
    """Independent full/half/half2 reference for the adaptive probe topology."""
    v_full = _adapt_implicit_midpoint(_ADAPT_V0, _ADAPT_DT)
    v_half = _adapt_implicit_midpoint(_ADAPT_V0, _ADAPT_DT / 2.0)
    v_half2 = _adapt_implicit_midpoint(v_half, _ADAPT_DT / 2.0)
    flow_half1 = _adapt_gate_flow(0.5 * (_ADAPT_V0 + v_half))
    flow_half2 = _adapt_gate_flow(0.5 * (v_half + v_half2))
    raw_difference = abs(v_half2 - v_full)
    return {
        "v_full": v_full,
        "v_half": v_half,
        "v_half2": v_half2,
        "flow_half1": flow_half1,
        "flow_half2": flow_half2,
        "raw_difference": raw_difference,
        "external_half": (_ADAPT_DT / 2.0) * flow_half1 + (_ADAPT_DT / 2.0) * flow_half2,
    }


def _adapt_probe_topology() -> dict[str, Any]:
    return {
        "schema_version": 4,
        "gravity_m_s2": _ADAPT_G,
        "nodes": [
            {
                "node_id": "pool",
                "node_type": "storage",
                "initial_level_m": 5.0,
                "storage_curve_revision": 1,
                "storage_curve": [
                    {"level_m": 0.0, "volume_m3": 0.0},
                    {"level_m": 20.0, "volume_m3": 2000.0},
                ],
            },
            {"node_id": "source", "node_type": "boundary", "initial_level_m": _ADAPT_H_SOURCE},
        ],
        "links": [
            {
                "link_id": "gate_in",
                "link_type": "gate",
                "from_node": "source",
                "to_node": "pool",
                "discharge_coefficient": 0.8,
                "area_m2": 1.0,
                "initial_control": 1.0,
                "maximum_abs_flow_m3_s": 50.0,
            }
        ],
        "initial_inflows": [{"node_id": "pool", "flow_m3_s": 0.0}],
    }


def _write_adapt_case(
    work_path: Path,
    *,
    volume_abs_tolerance_m3: float,
    volume_rel_tolerance: float,
    initial_step_s: float,
    minimum_step_s: float,
    maximum_step_s: float = 120.0,
) -> tuple[Path, Path]:
    """Write adaptive probe topology/forcing/case; return (case_path, out_path)."""
    _candidate_writable(work_path)
    topo_path = work_path / "adapt_topology.json"
    force_path = work_path / "adapt_forcing.jsonl"
    case_path = work_path / "adapt_case.json"
    out_path = work_path / "adapt_report.json"
    _write_json(topo_path, _adapt_probe_topology())
    _noop_forcing(force_path, link_id="gate_in")
    case = {
        "schema_version": 4,
        "case_id": "adapt-step-doubling-probe",
        "start_time_s": 0,
        "end_time_s": 20,
        "output_interval_s": 600,
        "topology_path": str(topo_path.resolve()),
        "forcing_path": str(force_path.resolve()),
        "solver": {
            "initial_step_s": initial_step_s,
            "minimum_step_s": minimum_step_s,
            "maximum_step_s": maximum_step_s,
            "volume_abs_tolerance_m3": volume_abs_tolerance_m3,
            "volume_rel_tolerance": volume_rel_tolerance,
            "newton_abs_tolerance_m3": 1e-12,
            "newton_rel_tolerance": 1e-14,
            "maximum_newton_iterations": 40,
        },
    }
    _write_json(case_path, case)
    return case_path, out_path


@pytest.mark.parametrize(
    "desired_error,expected_next",
    [
        (0.01, 40.0),
        (0.25, 20.0),
        (0.75, 10.0),
    ],
)
def test_binary_adaptive_acceptance_thresholds(
    work_path: Path, desired_error: float, expected_next: float
) -> None:
    """Step doubling must commit V_half2, half-step conservation, and threshold next_step_s."""
    ref = _adapt_reference()
    assert ref["raw_difference"] > 1e-4, (
        "probe raw |V_half2-V_full| must exceed report serialization precision"
    )
    vol_abs = ref["raw_difference"] / desired_error
    case_path, out_path = _write_adapt_case(
        work_path,
        volume_abs_tolerance_m3=vol_abs,
        volume_rel_tolerance=0.0,
        initial_step_s=_ADAPT_DT,
        minimum_step_s=0.46875,
        maximum_step_s=120.0,
    )
    snap_path = work_path / "adapt_snap.json"
    proc = run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--stop-at",
            "20",
            "--output",
            str(out_path.resolve()),
            "--snapshot-out",
            str(snap_path.resolve()),
        ],
        check=False,
    )
    assert proc.returncode == 0, f"adaptive accept failed:\n{proc.stderr}\n{proc.stdout}"
    report = json.loads(out_path.read_text())
    snap = json.loads(snap_path.read_text())
    final = report["samples"][-1]
    pool = _node_by_id(final, "pool")
    # Report sample floats are round-half-even then streamed with default C++
    # precision (~6 significant digits). Stay far tighter than the V_full gap.
    vol_tol = 5e-4
    assert pool["volume_m3"] == pytest.approx(ref["v_half2"], abs=vol_tol)
    assert abs(pool["volume_m3"] - ref["v_full"]) > 1e-2, (
        "committed volume must not match the rejected full-step V_full shortcut"
    )
    assert final["conservation"]["cumulative_external_volume_m3"] == pytest.approx(
        ref["external_half"], abs=vol_tol
    )
    assert report["diagnostics"]["accepted_substeps"] == 2
    assert report["diagnostics"]["rejected_attempts"] == 0
    assert snap["solver_state"]["next_step_s"] == pytest.approx(expected_next, abs=1e-12)
    assert abs(final["conservation"]["mass_residual_m3"]) < 1e-6
    assert report["diagnostics"]["maximum_abs_mass_residual_m3"] < 1e-6


def test_binary_adaptive_error_rejection_preserves_sentinel(work_path: Path) -> None:
    """Normalized error > 1 must reject once and fail min-step without rewriting output."""
    ref = _adapt_reference()
    vol_abs = ref["raw_difference"] / 2.0
    case_path, out_path = _write_adapt_case(
        work_path,
        volume_abs_tolerance_m3=vol_abs,
        volume_rel_tolerance=0.0,
        initial_step_s=_ADAPT_DT,
        minimum_step_s=_ADAPT_DT,
        maximum_step_s=120.0,
    )
    sentinel = b"SENTINEL_ADAPT_REJECT_OUTPUT_UNCHANGED\n"
    out_path.write_bytes(sentinel)
    os.chmod(out_path, 0o666)
    proc = run_lockctl(
        [
            "run",
            "--case",
            str(case_path.resolve()),
            "--stop-at",
            "20",
            "--output",
            str(out_path.resolve()),
        ],
        check=False,
    )
    assert proc.returncode != 0, "error>1 with min_step==dt must fail after rejection"
    assert out_path.read_bytes() == sentinel, (
        "rejected adaptive candidate must not replace a pre-existing output file"
    )
