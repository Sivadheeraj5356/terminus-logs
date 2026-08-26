"""Behavioral tests for polymorph-chronicle fuse pipeline (trace ingest, peak capture, chronicle export)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "verifier-support"))
from b6lc_chronicle_ref import (  # noqa: E402
    adjacency_batch_map,
    audit_commitment,
    build_concordance_cycle_basis,
    build_cross_batch_concordance,
    build_hold_adjacency,
    build_hold_spine,
    build_peak_capture,
    closure_bundle_digest,
    expected_bundled_chronicle,
    lattice_residuals,
    ledger_triad_digest,
    load_trace_events,
    manifest_bind_digest,
    phase_seal,
    reference_fuse,
    topology_bundle_digest,
)

APP = Path("/app")
TOOL = APP / "bin" / "polymorph-chronicle"
FORM = APP / "lattice-invariant-catalog" / "formulation-catalog.json"
WINDOW = APP / "conching-network" / "conching-window-table.json"
BATCHES = APP / "kiln-run-traces"
CAPTURE = APP / "state" / "dsc-peak-capture.json"
RESIDUAL = APP / "state" / "torque-residual-snapshot.json"
SEAL = APP / "state" / "polymorph-walk-seal.json"
MANIFEST = APP / "state" / "chronicle-bind-manifest.json"
ATLAS = APP / "output" / "lattice-chronicle-report.json"
SPINE = APP / "state" / "hold-spine-ledger.json"
ADJACENCY = APP / "state" / "hold-adjacency-ledger.json"
CONCORDANCE = APP / "state" / "cross-batch-concordance.json"
CYCLES = APP / "state" / "concordance-cycle-basis.json"
EPOCH = APP / "var" / "walk_epoch"
AUDIT = APP / "var" / "chronicle-audit.log.jsonl"
ZONE_B6 = Path("/opt/verifier-fixtures/b6lc-probes/zone-poly-window-trap")
B6LC_PROBE_WINDOW = ZONE_B6 / "conching-window-table.json"
B6LC_PROBE_BATCHES = Path("/opt/verifier-fixtures/b6lc-probes/poison-batch-trap")
B6LC_ORDER_TRAP = Path("/opt/verifier-fixtures/b6lc-probes/trace-order-trap")
B6LC_SHEAR_TRAP = Path("/opt/verifier-fixtures/b6lc-probes/shear-bonus-trap")
B6LC_QUENCH_TRAP = Path("/opt/verifier-fixtures/b6lc-probes/quench-scale-trap")
B6LC_ADJ_TRAP = Path("/opt/verifier-fixtures/b6lc-probes/adjacency-gap-trap")


def path_content_fingerprint(path: Path) -> str:
    """SHA-256 fingerprint of a file or of every file under a directory tree."""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    lines: list[str] = []
    for fp in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = fp.relative_to(path).as_posix()
        digest = hashlib.sha256(fp.read_bytes()).hexdigest()
        lines.append(f"{rel}:{digest}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def protect_input_path(src: Path, dest_root: Path) -> Path:
    """Copy a writable input into a protected verifier-owned tree before the tool runs."""
    dest = dest_root / src.name
    if src.is_file():
        dest.write_bytes(src.read_bytes())
    else:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return dest


def protect_inputs(*sources: Path) -> tuple[Path, dict[Path, Path], dict[Path, str]]:
    """
    Snapshot writable inputs under a fresh temp tree before submission runs.

    Returns (root, original->protected map, original->pre-run fingerprint map).
    Expectations must use protected paths. Integrity checks compare live fingerprints.
    """
    root = Path(tempfile.mkdtemp(prefix="b6lc-protected-"))
    mapping: dict[Path, Path] = {}
    fingerprints: dict[Path, str] = {}
    for src in sources:
        fingerprints[src] = path_content_fingerprint(src)
        mapping[src] = protect_input_path(src, root)
    return root, mapping, fingerprints


def assert_inputs_unchanged(fingerprints: dict[Path, str]) -> None:
    """Fail if the submission mutated writable fixture inputs under test."""
    for path, before in fingerprints.items():
        after = path_content_fingerprint(path)
        assert after == before, f"input mutated under test: {path}"


def run_bind(
    *,
    batches: Path = BATCHES,
    window: Path = WINDOW,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(TOOL),
        "bind",
        "--lattice-invariant-catalog",
        str(FORM),
        "--conching-window",
        str(window),
        "--kiln-traces",
        str(batches),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd="/app", env=env)


def run_emit(*, output: Path = ATLAS) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(TOOL),
        "emit",
        "--lattice-invariant-catalog",
        str(FORM),
        "--output",
        str(output),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd="/app")


def run_fuse(
    *,
    batches: Path = BATCHES,
    window: Path = WINDOW,
    output: Path = ATLAS,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        str(TOOL),
        "fuse",
        "--lattice-invariant-catalog",
        str(FORM),
        "--conching-window",
        str(window),
        "--kiln-traces",
        str(batches),
        "--output",
        str(output),
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd="/app")


@pytest.fixture(scope="session", autouse=True)
def _tool_executable() -> None:
    assert TOOL.is_file() and os.access(TOOL, os.X_OK)


def test_ta5fcde_tb6lc_f03a7e2a01_bundled_atlas_matches_reference() -> None:
    """Bundled fuse atlas must match independent reference_fuse."""
    root, protected, fps = protect_inputs(FORM, WINDOW, BATCHES)
    try:
        _, _, _, want, _, _ = reference_fuse(
            protected[FORM],
            protected[WINDOW],
            protected[BATCHES],
            1,
            bind_traces_path=BATCHES,
            bind_window_path=WINDOW,
        )
        proc = run_fuse()
        assert proc.returncode == 0, proc.stderr
        assert_inputs_unchanged(fps)
        got = json.loads(ATLAS.read_text(encoding="utf-8"))
        assert got == want
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ta5fcde_tb6lc_f03a7e2a02_betast_betasn_matches_reference() -> None:
    """dsc-peak-capture.json must match reference staging builder."""
    assert run_fuse().returncode == 0
    tw = json.loads(WINDOW.read_text(encoding="utf-8"))
    events = load_trace_events(BATCHES)
    want = build_peak_capture(events, tw["windows"], tw["shear_bonus_hz"])
    got = json.loads(CAPTURE.read_text(encoding="utf-8"))
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a03_lattice_residual_matches_reference() -> None:
    """/app/state/torque-residual-snapshot.json must match reference residual math."""
    assert run_fuse().returncode == 0
    assert str(RESIDUAL) == "/app/state/torque-residual-snapshot.json"
    tw = json.loads(WINDOW.read_text(encoding="utf-8"))
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    catalog = json.loads(FORM.read_text(encoding="utf-8"))
    adj = build_hold_adjacency(
        staging,
        float(tw.get("adjacency_gap_c", 1.5)),
        float(tw.get("adjacency_pair_weight", 0.01)),
    )
    want = lattice_residuals(staging, tw["windows"], catalog, adjacency_batch_map(adj))
    got = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a04_phase_seal_matches_reference() -> None:
    """polymorph-walk-seal phase_seal binds all ten closure fields."""
    assert run_fuse().returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bind_digest = manifest.get("bind_digest") or manifest_bind_digest(
        manifest.get("kiln_traces_path", str(BATCHES)),
        manifest.get("conching_window_path", str(WINDOW)),
    )
    spine = build_hold_spine(staging)
    tw = json.loads(WINDOW.read_text(encoding="utf-8"))
    adj = build_hold_adjacency(
        staging,
        float(tw.get("adjacency_gap_c", 1.5)),
        float(tw.get("adjacency_pair_weight", 0.01)),
    )
    concordance = build_cross_batch_concordance(staging, residual)
    cycles = build_concordance_cycle_basis(staging, concordance)
    want = phase_seal(
        staging["capture_digest"],
        residual["snapshot_digest"],
        1,
        bind_digest,
        spine["spine_digest"],
        adj["adjacency_digest"],
        concordance["concordance_digest"],
        cycles["cycle_digest"],
    )
    got = json.loads(SEAL.read_text(encoding="utf-8"))
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a05_betaep_advances_after_betare() -> None:
    """walk_epoch must increment after each successful fuse."""
    EPOCH.write_text("1\n", encoding="utf-8")
    assert run_fuse().returncode == 0
    assert EPOCH.read_text(encoding="utf-8").strip() == "2"


def test_ta5fcde_tb6lc_f03a7e2a06_betaau_log_appends_betare_entry() -> None:
    """Audit jsonl must gain one fuse row with chronicle_digest and epoch pair matching the seal."""
    assert run_fuse().returncode == 0
    lines = AUDIT.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    row = json.loads(lines[-1])
    assert row["action"] == "fuse"
    assert "chronicle_digest" in row
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    assert seal["audit_commitment"] == audit_commitment(int(row["epoch_before"]))
    assert int(row["epoch_after"]) == int(row["epoch_before"]) + 1


def test_ta5fcde_tb6lc_f03a7e2a07_stdout_emits_chronicle_betadi_line() -> None:
    """CLI stdout must print chronicle_digest= matching export file."""
    proc = run_fuse()
    assert proc.returncode == 0, proc.stderr
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    assert f"chronicle_digest={atlas['chronicle_digest']}" in proc.stdout


def test_ta5fcde_tb6lc_f03a7e2a08_all_output_paths_exist() -> None:
    """Fuse materializes every documented state and publish artifact."""
    assert run_fuse().returncode == 0
    assert str(CAPTURE) == "/app/state/dsc-peak-capture.json"
    assert str(SEAL) == "/app/state/polymorph-walk-seal.json"
    assert str(MANIFEST) == "/app/state/chronicle-bind-manifest.json"
    assert str(SPINE) == "/app/state/hold-spine-ledger.json"
    assert str(CYCLES) == "/app/state/concordance-cycle-basis.json"
    assert str(ATLAS) == "/app/output/lattice-chronicle-report.json"
    assert CAPTURE.is_file() and CAPTURE.stat().st_size > 32
    assert RESIDUAL.is_file() and RESIDUAL.stat().st_size > 32
    assert SPINE.is_file() and SPINE.stat().st_size > 32
    assert CYCLES.is_file() and CYCLES.stat().st_size > 32
    assert SEAL.is_file() and SEAL.stat().st_size > 32
    assert MANIFEST.is_file() and MANIFEST.stat().st_size > 16
    assert ATLAS.is_file() and ATLAS.stat().st_size > 32


def test_ta5fcde_tb6lc_f03a7e2a09_betast_excludes_marker_events() -> None:
    """MARKER events must not inflate event_count in staging."""
    assert run_fuse().returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    beta = next(b for b in staging["batches"] if b["batch_id"] == "BETA-02")
    assert beta["event_count"] == 4


def test_ta5fcde_tb6lc_f03a7e2a10_three_batches_in_betast() -> None:
    """Bundled batches directory yields three distinct batch_ids in staging."""
    assert run_fuse().returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    ids = sorted(b["batch_id"] for b in staging["batches"])
    assert ids == ["ALPHA-01", "BETA-02", "GAMMA-03"]


def test_ta5fcde_tb6lc_f03a7e2a11_transition_flags_present() -> None:
    """Atlas lattice_walks must include boolean transition per batch."""
    assert run_fuse().returncode == 0
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    for track in atlas["lattice_walks"]:
        assert isinstance(track["transition"], bool)


def test_ta5fcde_tb6lc_f03a7e2a12_alpha_seed_differs_from_dominant() -> None:
    """ALPHA-01 seed V should transition under bundled holds."""
    assert run_fuse().returncode == 0
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    alpha = next(t for t in atlas["lattice_walks"] if t["batch_id"] == "ALPHA-01")
    assert alpha["transition"] is True


def test_ta5fcde_tb6lc_f03a7e2a13_betare_persistence_second_run() -> None:
    """Second fuse on same inputs must advance epoch and audit sequence."""
    assert run_fuse().returncode == 0
    first_epoch = EPOCH.read_text(encoding="utf-8").strip()
    assert run_fuse().returncode == 0
    second_epoch = EPOCH.read_text(encoding="utf-8").strip()
    assert int(second_epoch) == int(first_epoch) + 1


def test_ta5fcde_tb6lc_f03a7e2a14_cross_run_betaau_grows() -> None:
    """Cross-run fuse must append multiple audit jsonl lines."""
    assert run_fuse().returncode == 0
    assert run_fuse().returncode == 0
    lines = AUDIT.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2


def test_ta5fcde_tb6lc_f03a7e2a15_seal_rewritten_after_tamper() -> None:
    """Replay must rewrite a tampered polymorph-walk-seal.json correctly."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    seal["phase_seal"] = "0" * 64
    SEAL.write_text(json.dumps(seal) + "\n", encoding="utf-8")
    assert run_fuse().returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    got = json.loads(SEAL.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bind_digest = manifest.get("bind_digest") or manifest_bind_digest(
        manifest.get("kiln_traces_path", str(BATCHES)),
        manifest.get("conching_window_path", str(WINDOW)),
    )
    spine = json.loads(SPINE.read_text(encoding="utf-8"))
    adj = json.loads(ADJACENCY.read_text(encoding="utf-8"))
    concordance = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    cycles = json.loads(CYCLES.read_text(encoding="utf-8"))
    want = phase_seal(
        staging["capture_digest"],
        residual["snapshot_digest"],
        got["epoch"],
        bind_digest,
        spine["spine_digest"],
        adj["adjacency_digest"],
        concordance["concordance_digest"],
        cycles["cycle_digest"],
    )
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a18_betast_betadi_stable_on_repeat() -> None:
    """Staging capture_digest for fixed inputs stays stable when pre-emit epoch is restored."""
    assert run_fuse().returncode == 0
    d1 = json.loads(CAPTURE.read_text(encoding="utf-8"))["capture_digest"]
    EPOCH.write_text("1\n", encoding="utf-8")
    if AUDIT.exists():
        AUDIT.unlink()
    for path in (CAPTURE, RESIDUAL, SEAL, SPINE, ATLAS):
        if path.exists():
            path.unlink()
    assert run_fuse().returncode == 0
    d2 = json.loads(CAPTURE.read_text(encoding="utf-8"))["capture_digest"]
    assert d1 == d2


def test_ta5fcde_tb6lc_f03a7e2a16_tb3_zone_poly_window_trap() -> None:
    """ZONE-B6 fixture with stricter hold_min_s must change dominant polymorph."""
    assert B6LC_PROBE_WINDOW.is_file()
    proc = run_fuse(window=B6LC_PROBE_WINDOW, batches=B6LC_PROBE_BATCHES)
    assert proc.returncode == 0, proc.stderr
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    _, _, _, want, _, _ = reference_fuse(FORM, B6LC_PROBE_WINDOW, B6LC_PROBE_BATCHES, 1)
    assert atlas == want


def test_ta5fcde_tb6lc_f03a7e2a17_tb3_poison_batch_residual_score() -> None:
    """ZONE-B6 poison batch directory must score residual against trap window table."""
    assert run_fuse(window=B6LC_PROBE_WINDOW, batches=B6LC_PROBE_BATCHES).returncode == 0
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    assert residual["residuals"][0]["batch_id"] == "TRAP-99"


def test_ta5fcde_tb6lc_f03a7e2a18_chronicle_betadi_stable_on_repeat_inputs() -> None:
    """Chronicle digest matches when the same pre-emit walk_epoch is restored before the second fuse."""
    assert run_fuse().returncode == 0
    d1 = json.loads(ATLAS.read_text())["chronicle_digest"]
    EPOCH.write_text("1\n", encoding="utf-8")
    if AUDIT.exists():
        AUDIT.unlink()
    assert run_fuse().returncode == 0
    d2 = json.loads(ATLAS.read_text())["chronicle_digest"]
    assert d1 == d2


def test_ta5fcde_tb6lc_f03a7e2a19_decoy_flavor_not_in_atlas() -> None:
    """Atlas chronicle must not contain flavor_score fields from decoy module."""
    assert run_fuse().returncode == 0
    text = ATLAS.read_text(encoding="utf-8")
    assert "flavor_score" not in text


def test_ta5fcde_tb6lc_f03a7e2a20_betain_order_affects_betast() -> None:
    """Fuse peak capture must honor batch_id then cycle_seq then ts on out-of-order kiln traces."""
    assert B6LC_ORDER_TRAP.is_dir()
    assert run_fuse(batches=B6LC_ORDER_TRAP, window=WINDOW).returncode == 0
    got = json.loads(CAPTURE.read_text(encoding="utf-8"))
    windows = json.loads(WINDOW.read_text(encoding="utf-8"))
    want = build_peak_capture(
        load_trace_events(B6LC_ORDER_TRAP),
        windows["windows"],
        float(windows["shear_bonus_hz"]),
    )
    assert got == want
    holds = got["batches"][0]["hold_profiles"]
    assert [float(h["temp_c"]) for h in holds] == [37.0, 37.5, 32.0, 32.5]


def test_ta5fcde_tb6lc_f03a7e2a21_chronicle_digest_stable_on_repeat_inputs() -> None:
    """chronicle_digest matches across fuses when pre-emit walk_epoch is restored to the same integer."""
    assert run_fuse().returncode == 0
    d1 = json.loads(ATLAS.read_text(encoding="utf-8"))["chronicle_digest"]
    EPOCH.write_text("1\n", encoding="utf-8")
    if AUDIT.exists():
        AUDIT.unlink()
    for path in (CAPTURE, RESIDUAL, SEAL, SPINE):
        if path.exists():
            path.unlink()
    assert run_fuse().returncode == 0
    d2 = json.loads(ATLAS.read_text(encoding="utf-8"))["chronicle_digest"]
    assert d1 == d2


def test_ta5fcde_tb6lc_f03a7e2a26_walk_content_digest_matches_reference() -> None:
    """walk_content_digest must match independent SHA-256 over lattice_walks alone."""
    assert run_fuse().returncode == 0
    got = json.loads(ATLAS.read_text(encoding="utf-8"))
    want = expected_bundled_chronicle(1)
    assert got["walk_content_digest"] == want["walk_content_digest"]
    assert got["chronicle_digest"] == want["chronicle_digest"]
    assert got["walk_content_digest"] != got["chronicle_digest"]


def test_ta5fcde_tb6lc_f03a7e2a27_walk_content_stable_when_epoch_advances() -> None:
    """walk_content_digest stays fixed across a real epoch bump while chronicle_digest changes."""
    EPOCH.write_text("1\n", encoding="utf-8")
    assert run_fuse().returncode == 0
    first = json.loads(ATLAS.read_text(encoding="utf-8"))
    assert EPOCH.read_text(encoding="utf-8").strip() == "2"
    if AUDIT.exists():
        AUDIT.unlink()
    for path in (CAPTURE, RESIDUAL, SEAL, SPINE, ATLAS, MANIFEST):
        if path.exists():
            path.unlink()
    assert run_fuse().returncode == 0
    second = json.loads(ATLAS.read_text(encoding="utf-8"))
    assert EPOCH.read_text(encoding="utf-8").strip() == "3"
    assert first["walk_content_digest"] == second["walk_content_digest"]
    assert first["chronicle_digest"] != second["chronicle_digest"]
    assert second["epoch"] == 2


def test_ta5fcde_tb6lc_f03a7e2a22_bind_emit_matches_fuse() -> None:
    """Separate bind and emit must match one-shot fuse atlas."""
    assert run_bind().returncode == 0
    assert run_emit().returncode == 0
    got = json.loads(ATLAS.read_text(encoding="utf-8"))
    want = expected_bundled_chronicle(1)
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a23_emit_uses_staged_residual_snapshot() -> None:
    """emit uses staged residual rows under asymmetric trust; snapshot_digest may stay stale."""
    assert run_bind().returncode == 0
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    stale_digest = residual["snapshot_digest"]
    residual["residuals"][0]["residual_score"] = 999.0
    # Deliberately leave snapshot_digest unchanged so row content and digest disagree.
    RESIDUAL.write_text(json.dumps(residual) + "\n", encoding="utf-8")
    assert run_emit().returncode == 0
    on_disk = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    assert on_disk["snapshot_digest"] == stale_digest
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    scores = {t["batch_id"]: t["residual_score"] for t in atlas["lattice_walks"]}
    assert scores[residual["residuals"][0]["batch_id"]] == 999.0


def test_ta5fcde_tb6lc_f03a7e2a24_manifest_records_window_path() -> None:
    """bind manifest must store conching_window_path for emit."""
    assert run_bind(window=B6LC_PROBE_WINDOW, batches=B6LC_PROBE_BATCHES).returncode == 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("conching_window_path") == str(B6LC_PROBE_WINDOW)


def test_ta5fcde_tb6lc_f03a7e2a25_tb3_bind_kiln_override() -> None:
    """TB3_KILN_TRACES during bind must stage poison batch TRAP-99."""
    env = os.environ.copy()
    env["TB3_KILN_TRACES"] = str(B6LC_PROBE_BATCHES)
    env["TB3_CONCHING_WINDOW"] = str(B6LC_PROBE_WINDOW)
    assert run_bind(batches=BATCHES, window=WINDOW, env=env).returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    ids = {b["batch_id"] for b in staging["batches"]}
    assert "TRAP-99" in ids
    assert run_emit().returncode == 0
    _, _, _, want, _, _ = reference_fuse(FORM, B6LC_PROBE_WINDOW, B6LC_PROBE_BATCHES, 1)
    assert json.loads(ATLAS.read_text(encoding="utf-8")) == want



def test_ta5fcde_tb6lc_f03a7e2a28_tb3_shear_bonus_gate() -> None:
    """ZONE shear-bonus trap: shear_hz below shear_bonus_hz must not credit bonus hold."""
    assert (B6LC_SHEAR_TRAP / "conching-window-table.json").is_file()
    window = B6LC_SHEAR_TRAP / "conching-window-table.json"
    batches = B6LC_SHEAR_TRAP
    root, protected, fps = protect_inputs(FORM, window, batches)
    try:
        _, _, _, atlas, _, _ = reference_fuse(
            protected[FORM],
            protected[window],
            protected[batches],
            1,
            bind_traces_path=batches,
            bind_window_path=window,
        )
        assert run_fuse(window=window, batches=batches).returncode == 0
        assert_inputs_unchanged(fps)
        got = json.loads(ATLAS.read_text(encoding="utf-8"))
        assert got == atlas
        holds = json.loads(CAPTURE.read_text(encoding="utf-8"))["batches"][0]["hold_profiles"]
        assert all(int(h["effective_hold_s"]) == 100 for h in holds)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ta5fcde_tb6lc_f03a7e2a29_quench_scale_on_walks() -> None:
    """Bundled lattice walks must carry formulation quench_scale from the catalog."""
    assert run_fuse().returncode == 0
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    want = expected_bundled_chronicle(1)
    assert atlas == want
    by_id = {t["batch_id"]: t for t in atlas["lattice_walks"]}
    assert by_id["ALPHA-01"]["quench_scale"] == 1.25
    assert by_id["BETA-02"]["quench_scale"] == 0.8


def test_ta5fcde_tb6lc_f03a7e2a30_tb3_quench_scale_residual() -> None:
    """ZONE quench trap: residual_score must multiply deviation*hold by catalog quench_scale."""
    catalog = B6LC_QUENCH_TRAP / "formulation-catalog.json"
    window = B6LC_QUENCH_TRAP / "conching-window-table.json"
    batches = B6LC_QUENCH_TRAP
    assert catalog.is_file() and window.is_file()
    root, protected, fps = protect_inputs(catalog, window, batches)
    try:
        _, _, _, want, _, _ = reference_fuse(
            protected[catalog],
            protected[window],
            protected[batches],
            1,
            bind_traces_path=batches,
            bind_window_path=window,
        )
        cmd = [
            str(TOOL),
            "fuse",
            "--lattice-invariant-catalog",
            str(catalog),
            "--conching-window",
            str(window),
            "--kiln-traces",
            str(batches),
            "--output",
            str(ATLAS),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd="/app")
        assert proc.returncode == 0, proc.stderr
        assert_inputs_unchanged(fps)
        got = json.loads(ATLAS.read_text(encoding="utf-8"))
        assert got == want
        assert got["lattice_walks"][0]["quench_scale"] == 2.0
        residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
        assert residual["residuals"][0]["residual_score"] == want["lattice_walks"][0]["residual_score"]
    finally:
        shutil.rmtree(root, ignore_errors=True)

def test_ta5fcde_tb6lc_f03a7e2a31_hold_spine_matches_reference() -> None:
    """hold-spine-ledger.json must match reference spine_seq ordering and spine_digest."""
    assert run_fuse().returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    want = build_hold_spine(staging)
    got = json.loads(SPINE.read_text(encoding="utf-8"))
    assert got == want


def test_ta5fcde_tb6lc_f03a7e2a32_emit_rejects_missing_hold_spine() -> None:
    """emit must fail when hold-spine-ledger.json is absent after bind."""
    assert run_bind().returncode == 0
    assert SPINE.is_file()
    SPINE.unlink()
    proc = run_emit()
    assert proc.returncode != 0, "emit must reject missing hold-spine ledger"


def test_ta5fcde_tb6lc_f03a7e2a33_emit_rejects_tampered_spine_digest() -> None:
    """emit must fail when spine_digest no longer matches ledger rows."""
    assert run_bind().returncode == 0
    spine = json.loads(SPINE.read_text(encoding="utf-8"))
    spine["spine_digest"] = "0" * 64
    SPINE.write_text(json.dumps(spine) + "\n", encoding="utf-8")
    proc = run_emit()
    assert proc.returncode != 0, "emit must reject tampered spine_digest"


def test_ta5fcde_tb6lc_f03a7e2a34_seal_carries_spine_digest() -> None:
    """polymorph-walk-seal must record spine_digest matching the hold-spine ledger."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    spine = json.loads(SPINE.read_text(encoding="utf-8"))
    assert seal.get("spine_digest") == spine["spine_digest"]


def test_ta5fcde_tb6lc_f03a7e2a35_tb3_spine_order_trap() -> None:
    """Hidden order-trap fixtures must produce spine_seq matching capture hold order."""
    assert B6LC_ORDER_TRAP.is_dir()
    assert run_fuse(batches=B6LC_ORDER_TRAP, window=WINDOW).returncode == 0
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    want = build_hold_spine(staging)
    got = json.loads(SPINE.read_text(encoding="utf-8"))
    assert got == want
    temps = [float(r["temp_c"]) for r in got["rows"]]
    assert temps == [37.0, 37.5, 32.0, 32.5]


def test_ta5fcde_tb6lc_f03a7e2a36_hold_adjacency_matches_reference() -> None:
    """hold-adjacency-ledger.json must match consecutive HOLD gap pairing reference."""
    assert run_fuse().returncode == 0
    assert Path("/app/state/hold-adjacency-ledger.json").is_file()
    assert Path("/app/state/polymorph-walk-seal.json").is_file()
    staging = json.loads(CAPTURE.read_text(encoding="utf-8"))
    tw = json.loads(WINDOW.read_text(encoding="utf-8"))
    want = build_hold_adjacency(
        staging,
        float(tw.get("adjacency_gap_c", 1.5)),
        float(tw.get("adjacency_pair_weight", 0.01)),
    )
    got = json.loads(ADJACENCY.read_text(encoding="utf-8"))
    assert got == want
    assert len(got["pairs"]) >= 1
    assert Path("/app/state/hold-adjacency-ledger.json").resolve() == ADJACENCY.resolve()


def test_ta5fcde_tb6lc_f03a7e2a37_emit_rejects_missing_adjacency() -> None:
    """emit must fail when hold-adjacency-ledger.json is absent after bind."""
    assert run_bind().returncode == 0
    assert ADJACENCY.is_file()
    ADJACENCY.unlink()
    proc = run_emit()
    assert proc.returncode != 0, "emit must reject missing hold-adjacency ledger"


def test_ta5fcde_tb6lc_f03a7e2a38_emit_rejects_tampered_adjacency_digest() -> None:
    """emit must fail when adjacency_digest no longer matches ledger pairs."""
    assert run_bind().returncode == 0
    ledger = json.loads(ADJACENCY.read_text(encoding="utf-8"))
    ledger["adjacency_digest"] = "0" * 64
    ADJACENCY.write_text(json.dumps(ledger) + "\n", encoding="utf-8")
    proc = run_emit()
    assert proc.returncode != 0, "emit must reject tampered adjacency_digest"


def test_ta5fcde_tb6lc_f03a7e2a39_seal_carries_adjacency_digest() -> None:
    """polymorph-walk-seal must record adjacency_digest matching the adjacency ledger."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    adj = json.loads(ADJACENCY.read_text(encoding="utf-8"))
    assert seal.get("adjacency_digest") == adj["adjacency_digest"]


def test_ta5fcde_tb6lc_f03a7e2a40_tb3_adjacency_gap_trap() -> None:
    """Hidden adjacency trap: large consecutive HOLD gaps must couple into residual_score."""
    assert B6LC_ADJ_TRAP.is_dir()
    window = B6LC_ADJ_TRAP / "conching-window-table.json"
    batches = B6LC_ADJ_TRAP
    root, protected, fps = protect_inputs(FORM, window, batches)
    try:
        _, _, _, want, _, adj = reference_fuse(
            protected[FORM],
            protected[window],
            protected[batches],
            1,
            bind_traces_path=batches,
            bind_window_path=window,
        )
        assert run_fuse(window=window, batches=batches).returncode == 0
        assert_inputs_unchanged(fps)
        got = json.loads(ATLAS.read_text(encoding="utf-8"))
        assert got == want
        on_disk = json.loads(ADJACENCY.read_text(encoding="utf-8"))
        assert on_disk["adjacency_digest"] == adj["adjacency_digest"]
        assert float(got["lattice_walks"][0]["residual_score"]) > 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ta5fcde_tb6lc_f03a7e2a41_tb3_audit_commitment_seal_trap() -> None:
    """Hidden trap: phase_seal must bind audit_commitment for fuse|epoch_before|epoch_after."""
    EPOCH.write_text("3\n", encoding="utf-8")
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    assert seal["epoch"] == 3
    assert seal["audit_commitment"] == audit_commitment(3)
    row = json.loads(AUDIT.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["epoch_before"] == 3
    assert row["epoch_after"] == 4


def test_ta5fcde_tb6lc_f03a7e2a42_tb3_ledger_triad_seal_trap() -> None:
    """Hidden trap: phase_seal must bind ledger_triad_digest over bind|spine|adjacency."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    spine = json.loads(SPINE.read_text(encoding="utf-8"))
    adj = json.loads(ADJACENCY.read_text(encoding="utf-8"))
    concordance = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    cycles = json.loads(CYCLES.read_text(encoding="utf-8"))
    want_triad = ledger_triad_digest(
        manifest["bind_digest"],
        spine["spine_digest"],
        adj["adjacency_digest"],
    )
    assert seal["ledger_triad_digest"] == want_triad
    want = phase_seal(
        seal["capture_digest"],
        seal["snapshot_digest"],
        int(seal["epoch"]),
        manifest["bind_digest"],
        spine["spine_digest"],
        adj["adjacency_digest"],
        concordance["concordance_digest"],
        cycles["cycle_digest"],
    )
    assert seal["phase_seal"] == want["phase_seal"]
    want_topology = topology_bundle_digest(
        concordance["concordance_digest"], cycles["cycle_digest"]
    )
    assert seal["topology_bundle_digest"] == want_topology
    assert seal["closure_bundle_digest"] == closure_bundle_digest(want_triad, want_topology)
    # Legacy eight-field preimage must not match the concordance-bound seal.
    legacy = hashlib.sha256(
        f"{seal['capture_digest']}|{seal['snapshot_digest']}|{seal['epoch']}|"
        f"{manifest['bind_digest']}|{spine['spine_digest']}|{adj['adjacency_digest']}|"
        f"{seal['audit_commitment']}".encode()
    ).hexdigest()
    assert seal["phase_seal"] != legacy


def test_ta5fcde_tb6lc_f03a7e2a43_cross_batch_concordance_matches_reference() -> None:
    """The staged cross-batch concordance artifact must match independent pairwise math."""
    assert run_fuse().returncode == 0
    assert str(CONCORDANCE) == "/app/state/cross-batch-concordance.json"
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    assert json.loads(CONCORDANCE.read_text(encoding="utf-8")) == (
        build_cross_batch_concordance(capture, residual)
    )


def test_ta5fcde_tb6lc_f03a7e2a44_concordance_rows_are_complete_and_ordered() -> None:
    """Every unordered batch pair appears once in left/right lexical order."""
    assert run_fuse().returncode == 0
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    ledger = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    batch_ids = sorted(row["batch_id"] for row in capture["batches"])
    expected_pairs = [
        (left, right)
        for i, left in enumerate(batch_ids)
        for right in batch_ids[i + 1 :]
    ]
    got_pairs = [
        (row["left_batch_id"], row["right_batch_id"]) for row in ledger["rows"]
    ]
    assert got_pairs == expected_pairs
    assert all(row["shared_polymorphs"] == sorted(row["shared_polymorphs"]) for row in ledger["rows"])


def test_ta5fcde_tb6lc_f03a7e2a45_emit_rejects_missing_concordance() -> None:
    """Emit must refuse a missing concordance stage without advancing or replacing output."""
    assert run_fuse().returncode == 0
    before_epoch = EPOCH.read_text(encoding="utf-8")
    before_report = ATLAS.read_bytes()
    CONCORDANCE.unlink()
    proc = run_emit()
    assert proc.returncode != 0
    assert EPOCH.read_text(encoding="utf-8") == before_epoch
    assert ATLAS.read_bytes() == before_report


def test_ta5fcde_tb6lc_f03a7e2a46_emit_rejects_tampered_concordance_rows() -> None:
    """Changing a staged concordance value must fail digest and reference verification."""
    assert run_fuse().returncode == 0
    before_epoch = EPOCH.read_text(encoding="utf-8")
    ledger = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    assert ledger["rows"]
    ledger["rows"][0]["shared_effective_hold_s"] += 1
    CONCORDANCE.write_text(json.dumps(ledger) + "\n", encoding="utf-8")
    proc = run_emit()
    assert proc.returncode != 0
    assert EPOCH.read_text(encoding="utf-8") == before_epoch


def test_ta5fcde_tb6lc_f03a7e2a47_seal_binds_concordance_bundle() -> None:
    """The phase seal must carry both the concordance and derived closure-bundle digests."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    ledger = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    cycles = json.loads(CYCLES.read_text(encoding="utf-8"))
    assert seal["concordance_digest"] == ledger["concordance_digest"]
    topology = topology_bundle_digest(
        ledger["concordance_digest"], cycles["cycle_digest"]
    )
    assert seal["topology_bundle_digest"] == topology
    assert seal["closure_bundle_digest"] == closure_bundle_digest(
        seal["ledger_triad_digest"], topology
    )


def test_ta5fcde_tb6lc_f03a7e2a48_hidden_concordance_matches_reference() -> None:
    """Hidden quench geometry must alter residual distance and match concordance reference."""
    catalog = B6LC_QUENCH_TRAP / "formulation-catalog.json"
    window = B6LC_QUENCH_TRAP / "conching-window-table.json"
    proc = subprocess.run(
        [
            str(TOOL),
            "fuse",
            "--lattice-invariant-catalog",
            str(catalog),
            "--conching-window",
            str(window),
            "--kiln-traces",
            str(B6LC_QUENCH_TRAP),
            "--output",
            str(ATLAS),
        ],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    assert proc.returncode == 0, proc.stderr
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    residual = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    assert json.loads(CONCORDANCE.read_text(encoding="utf-8")) == (
        build_cross_batch_concordance(capture, residual)
    )


def test_ta5fcde_tb6lc_f03a7e2a49_cycle_basis_matches_reference() -> None:
    """Triple closure must match independent capture and pair-edge reference math."""
    assert run_fuse().returncode == 0
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    concordance = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    assert json.loads(CYCLES.read_text(encoding="utf-8")) == (
        build_concordance_cycle_basis(capture, concordance)
    )


def test_ta5fcde_tb6lc_f03a7e2a50_cycle_rows_cover_ordered_triples() -> None:
    """Every lexical batch triple appears once with its three canonical edges."""
    assert run_fuse().returncode == 0
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    basis = json.loads(CYCLES.read_text(encoding="utf-8"))
    ids = sorted(batch["batch_id"] for batch in capture["batches"])
    expected = [
        [left, middle, right]
        for i, left in enumerate(ids)
        for j, middle in enumerate(ids[i + 1 :], start=i + 1)
        for right in ids[j + 1 :]
    ]
    assert [row["batch_ids"] for row in basis["rows"]] == expected
    for row in basis["rows"]:
        a, b, c = row["batch_ids"]
        assert row["edge_pairs"] == [f"{a}|{b}", f"{a}|{c}", f"{b}|{c}"]


def test_ta5fcde_tb6lc_f03a7e2a51_emit_rejects_missing_cycle_basis() -> None:
    """Emit must stop before report replacement and epoch bump when cycles are absent."""
    assert run_fuse().returncode == 0
    before_report = ATLAS.read_bytes()
    before_epoch = EPOCH.read_text(encoding="utf-8")
    CYCLES.unlink()
    proc = run_emit()
    assert proc.returncode != 0
    assert ATLAS.read_bytes() == before_report
    assert EPOCH.read_text(encoding="utf-8") == before_epoch


def test_ta5fcde_tb6lc_f03a7e2a52_cycle_capture_projection_is_rederived() -> None:
    """A self-consistent digest cannot hide a changed triple hold projection."""
    assert run_fuse().returncode == 0
    basis = json.loads(CYCLES.read_text(encoding="utf-8"))
    assert basis["rows"]
    basis["rows"][0]["common_effective_hold_s"] += 1
    payload = {"schema": basis["schema"], "rows": basis["rows"]}
    basis["cycle_digest"] = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    CYCLES.write_text(json.dumps(basis) + "\n", encoding="utf-8")
    assert run_emit().returncode != 0


def test_ta5fcde_tb6lc_f03a7e2a53_cycle_edges_follow_staged_concordance() -> None:
    """Coordinated pair-ledger edits must invalidate the dependent cycle commitments."""
    assert run_fuse().returncode == 0
    concordance = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    assert concordance["rows"]
    concordance["rows"][0]["concordance_score"] = 0.123456
    payload = {"schema": concordance["schema"], "rows": concordance["rows"]}
    concordance["concordance_digest"] = hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    CONCORDANCE.write_text(json.dumps(concordance) + "\n", encoding="utf-8")
    assert run_emit().returncode != 0


def test_ta5fcde_tb6lc_f03a7e2a54_seal_binds_cycle_topology() -> None:
    """Cycle and pair digests must jointly determine the topology and phase seals."""
    assert run_fuse().returncode == 0
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    concordance = json.loads(CONCORDANCE.read_text(encoding="utf-8"))
    cycles = json.loads(CYCLES.read_text(encoding="utf-8"))
    topology = topology_bundle_digest(
        concordance["concordance_digest"], cycles["cycle_digest"]
    )
    assert seal["schema"] == "phase-stabilization-seal-v2"
    assert seal["cycle_digest"] == cycles["cycle_digest"]
    assert seal["topology_bundle_digest"] == topology
    assert seal["closure_bundle_digest"] == closure_bundle_digest(
        seal["ledger_triad_digest"], topology
    )
