"""Fleet rollout / daemon lifecycle verifier for k9 operational seal; reference_* + subprocess CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

INVOKE = "/app/environment/tools/k9_invoke"
EMIT = "/app/environment/tools/k9_emit"
RECOVER = "/app/environment/tools/k9_recover"
OUT = Path("/app/output/k9_trace.json")
SEQ_ROOT = Path("/app/cases/seq")
# Hidden traps: TB3_FIXTURE_ROOT overrides verifier-only ledger overlays (not public fixtures).
HIDDEN_SEQ = Path(os.environ.get("TB3_FIXTURE_ROOT", "/tests/hidden/seq"))
STATE = Path("/app/desk-state")
WAL_SEP = "\t"
DIGEST_REF = "/app/docs/digest_ref.sh"
MANIFEST = Path("/tests/hidden/fixture_manifest.sha256")

_ROW_REF = Path(__file__).resolve().parent / "hidden" / "row_canon.py"


def reference_call(mode: str, *args: str) -> object:
    out = subprocess.check_output(
        [sys.executable, str(_ROW_REF), mode, *args],
        text=True,
        timeout=30,
    )
    return json.loads(out)


def reference_epoch(n: int, ledger_overlay: int | None = None) -> list[dict]:
    if ledger_overlay is None:
        return reference_call("epoch", str(n))
    return reference_call("epoch", str(n), str(ledger_overlay))


def reference_full(ledger_overlay: int | None = None) -> list[dict]:
    if ledger_overlay is None:
        return reference_call("full")
    return reference_call("full", str(ledger_overlay))


def reference_full_multi(*overlay_indices: int) -> list[dict]:
    return reference_call("full_multi", *[str(i) for i in overlay_indices])


@pytest.fixture(scope="session", autouse=True)
def _rebuild_tools_from_source() -> None:
    """Fail the session if release rebuild fails; never grade against stale image binaries."""
    subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd="/app/environment",
        check=True,
        timeout=600,
        env=os.environ,
    )


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sort_rows(rows: list[dict]) -> list[dict]:
    phase_order = {"sk8": 0, "fp3": 1, "sr5": 2, "xr4": 3}
    return sorted(
        rows,
        key=lambda r: (
            r["scenario"],
            phase_order.get(r["phase"], 9),
            r["target"],
            r["marker"],
            r["sequence"],
        ),
    )


def _chain_fingerprint(rows: list[dict]) -> str:
    parts = [
        f"{r['scenario']},{r['phase']},{r['target']},{r['marker']},{r['sequence']}"
        for r in rows
    ]
    parts.sort()
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write("\n".join(parts) + "\n")
        tmp_path = tmp.name
    try:
        out = subprocess.check_output(
            [DIGEST_REF, "chain", tmp_path],
            text=True,
            timeout=30,
        )
        return out.strip()
    finally:
        os.unlink(tmp_path)


def _wal_crc(payload: str) -> int:
    out = subprocess.check_output(
        [DIGEST_REF, "crc", payload],
        text=True,
        timeout=30,
    )
    return int(out.strip())


def _wal_records() -> list[dict]:
    wal_path = STATE / "wal" / "chain.wal"
    out: list[dict] = []
    for raw in wal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        json_part, crc_part = raw.split(WAL_SEP, 1)
        rec = json.loads(json_part)
        payload = f"{rec['scenario']}:{rec['step']}:{rec['seq']}"
        assert int(crc_part.strip()) == _wal_crc(payload)
        out.append(rec)
    return out


def _reset_workspace() -> None:
    if OUT.exists():
        OUT.unlink()
    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True, exist_ok=True)


def _invoke_scenario(n: int) -> None:
    subprocess.run([INVOKE, "--scenario", str(n)], check=True)
    assert (STATE / f"epoch_{n}.json").is_file()


def _desk_run_in_order(order: list[int]) -> None:
    for n in order:
        _invoke_scenario(n)


def _emit_report() -> dict:
    subprocess.run([EMIT, "--out", "/app/output/k9_trace.json"], check=True)
    return _load_json(OUT)


def _epoch_rows(n: int) -> list[dict]:
    return _load_json(STATE / f"epoch_{n}.json")


def _read_checkpoint() -> dict:
    return _load_json(STATE / "checkpoint.json")


def _phase_rows(rows: list[dict], phase: str) -> list[dict]:
    return [r for r in rows if r["phase"] == phase]


def _row_by_marker(rows: list[dict], marker: str) -> dict:
    matches = [r for r in rows if r["marker"] == marker]
    assert len(matches) == 1
    return matches[0]


def _wal_steps(n: int) -> list[str]:
    return [rec["step"] for rec in _wal_records() if rec["scenario"] == n]


def _sha256_file(path: Path) -> str:
    out = subprocess.check_output(["sha256sum", str(path)], text=True, timeout=30)
    return out.split()[0]


def _tamper_s1_wal_release_done_swap() -> None:
    wal_path = STATE / "wal" / "chain.wal"
    lines_out: list[str] = []
    for raw in wal_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        json_part, _crc = raw.split(WAL_SEP, 1)
        rec = json.loads(json_part)
        if rec["scenario"] == 1 and rec["step"] == "release":
            rec["step"] = "done"
        elif rec["scenario"] == 1 and rec["step"] == "done":
            rec["step"] = "release"
        payload = f"{rec['scenario']}:{rec['step']}:{rec['seq']}"
        crc = _wal_crc(payload)
        lines_out.append(json.dumps(rec, separators=(",", ":")) + f"{WAL_SEP}{crc}")
    wal_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")


def _corrupt_middle_wal_crc() -> None:
    wal_path = STATE / "wal" / "chain.wal"
    lines = wal_path.read_text(encoding="utf-8").splitlines()
    mid = len(lines) // 2
    rec, _ = lines[mid].split(WAL_SEP, 1)
    lines[mid] = f"{rec}\t99999999"
    wal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _overlay_hidden_ledger(n: int) -> None:
    # Verifier-only ledger snapshot overlay (TB3_FIXTURE_ROOT / staging ingest export path).
    root = Path(os.environ.get("TB3_FIXTURE_ROOT", str(HIDDEN_SEQ)))
    shutil.copy2(root / f"s{n}" / "b0.evt", SEQ_ROOT / f"s{n}" / "b0.evt")


def test_te97f91_u00_public_manifest() -> None:
    """Public fixture bytes match the pinned manifest checksums."""
    assert MANIFEST.exists()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(maxsplit=1)
        assert _sha256_file(SEQ_ROOT / rel) == digest


def test_te97f91_u01_full_chain_rows() -> None:
    """Fleet rollout full-chain emit after hidden ledger overlay on index 1 matches reference."""
    assert "TB3_FIXTURE_ROOT" in os.environ or HIDDEN_SEQ.exists()
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([0, 1, 2, 3])
        report = _emit_report()
        expected = reference_full(1)
        assert _sort_rows(report["rows"]) == expected
        assert report["chain_fingerprint"] == _chain_fingerprint(expected)
    finally:
        dest.write_bytes(backup)


def test_te97f91_u02_per_index_epoch_rows() -> None:
    """Epoch caches match reference; index 1 uses overlay ledger bytes."""
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        for n in range(4):
            _invoke_scenario(n)
            overlay = 1 if n == 1 else None
            assert _sort_rows(_epoch_rows(n)) == _sort_rows(reference_epoch(n, overlay))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u03_reinvoke_slot_stable() -> None:
    """Second invoke of scenario 1 leaves epoch cache unchanged."""
    _reset_workspace()
    _invoke_scenario(1)
    first = _sort_rows(_epoch_rows(1))
    subprocess.run([INVOKE, "--scenario", "1"], check=True)
    second = _sort_rows(_epoch_rows(1))
    assert first == second == _sort_rows(reference_epoch(1))


def test_te97f91_u13_scrambled_desk_run_fp_stable() -> None:
    """Out-of-order desk_run with index-2 overlay yields stable chain fingerprint."""
    dest = SEQ_ROOT / "s2" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(2)
        _reset_workspace()
        _desk_run_in_order([0, 1, 2, 3])
        ordered = _emit_report()
        _reset_workspace()
        _overlay_hidden_ledger(2)
        _desk_run_in_order([2, 0, 1, 3])
        scrambled = _emit_report()
        assert scrambled["chain_fingerprint"] == ordered["chain_fingerprint"]
    finally:
        dest.write_bytes(backup)


def test_te97f91_u04_overlay_index_one_routing() -> None:
    """Hidden s1 ledger overlay recomputes rows and full-chain digest."""
    assert Path(os.environ.get("TB3_FIXTURE_ROOT", str(HIDDEN_SEQ))).is_dir()
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([0, 1, 2, 3])
        assert _sort_rows(_epoch_rows(1)) == _sort_rows(reference_epoch(1, ledger_overlay=1))
        report = _emit_report()
        assert report["chain_fingerprint"] == _chain_fingerprint(reference_full(1))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u14_restore_preserves_fp() -> None:
    """Recover after full desk_run preserves checkpoint seal and emit digest."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    warm = _emit_report()
    seal_before = _read_checkpoint()["order_seal"]
    subprocess.run([RECOVER], check=True)
    assert _read_checkpoint()["order_seal"] == seal_before
    cold = _emit_report()
    assert cold["chain_fingerprint"] == warm["chain_fingerprint"]


def test_te97f91_u15_double_run_idempotent() -> None:
    """Two consecutive export emits after the same ingest desk_run are identical snapshots."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    first = _emit_report()
    second = _emit_report()
    assert first == second


def test_te97f91_u16_restore_reinvoke_lineage() -> None:
    """Recover and re-invoke keep sk8 clean sequence stable for scenario 1."""
    _reset_workspace()
    _desk_run_in_order([0, 1])
    before = _row_by_marker(_phase_rows(_epoch_rows(1), "sk8"), "clean")
    subprocess.run([RECOVER], check=True)
    _invoke_scenario(1)
    after = _row_by_marker(_phase_rows(_epoch_rows(1), "sk8"), "clean")
    assert after == before


def test_te97f91_u17_tampered_log_blocks_output() -> None:
    """Daemon WAL step-order drift blocks emit."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    _emit_report()
    _tamper_s1_wal_release_done_swap()
    blocked = subprocess.run([EMIT, "--out", "/app/output/k9_trace.json"], check=False)
    assert blocked.returncode != 0


def test_te97f91_u18_tampered_log_blocks_restore() -> None:
    """Daemon WAL step-order drift blocks recover."""
    _reset_workspace()
    _invoke_scenario(1)
    _tamper_s1_wal_release_done_swap()
    assert subprocess.run([RECOVER], check=False).returncode != 0


def test_te97f91_u19_bad_crc_blocks_output() -> None:
    """Fleet config CRC drift on WAL blocks emit."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    _emit_report()
    wal_path = STATE / "wal" / "chain.wal"
    lines = wal_path.read_text(encoding="utf-8").splitlines()
    rec, _ = lines[0].split(WAL_SEP, 1)
    lines[0] = f"{rec}\t99999999"
    wal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert subprocess.run([EMIT, "--out", "/app/output/k9_trace.json"], check=False).returncode != 0


def test_te97f91_u20_bad_crc_blocks_restore() -> None:
    """Fleet config CRC drift on WAL blocks recover."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    _corrupt_middle_wal_crc()
    assert subprocess.run([RECOVER], check=False).returncode != 0


def test_te97f91_u21_output_spans_four_phases() -> None:
    """Rollout report includes all four phases for every scenario index."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    report = _emit_report()
    for n in range(4):
        rows = [r for r in report["rows"] if r["scenario"] == n]
        assert {r["phase"] for r in rows} == {"sk8", "fp3", "sr5", "xr4"}


def test_te97f91_u05_late_index_zero_stable() -> None:
    """Late index-zero invoke stays stable after overlay on index 1 in chain."""
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([1, 2, 3])
        _invoke_scenario(0)
        s0_first = _sort_rows(_epoch_rows(0))
        _invoke_scenario(0)
        assert _sort_rows(_epoch_rows(0)) == s0_first
        _desk_run_in_order([1, 2, 3])
        report = _emit_report()
        assert report["chain_fingerprint"] == _chain_fingerprint(reference_full(1))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u22_output_requires_all_epochs() -> None:
    """Emit refuses until epoch caches exist for indices 0 through 3."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2])
    assert subprocess.run([EMIT, "--out", "/app/output/k9_trace.json"], check=False).returncode != 0


def test_te97f91_u06_checkpoint_end_ordinal() -> None:
    """Recover rebuilds checkpoint wal_seq after drift; chain uses overlay index 1."""
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([0, 1, 2])
        drifted = _read_checkpoint()
        drifted["wal_seq"] = 0
        (STATE / "checkpoint.json").write_text(json.dumps(drifted) + "\n", encoding="utf-8")
        subprocess.run([RECOVER], check=True)
        assert _read_checkpoint()["wal_seq"] == _wal_records()[-1]["seq"]
        _invoke_scenario(3)
        report = _emit_report()
        assert report["chain_fingerprint"] == _chain_fingerprint(reference_full(1))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u07_partial_restore_full_rows() -> None:
    """Partial desk_run plus recover with overlay on index 1 allows full emit."""
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([0, 1])
        subprocess.run([RECOVER], check=True)
        _desk_run_in_order([2, 3])
        report = _emit_report()
        assert report["chain_fingerprint"] == _chain_fingerprint(reference_full(1))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u23_append_log_ordinal_monotonic() -> None:
    """Append-log sequence numbers are strictly increasing and unique."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    seqs = [rec["seq"] for rec in _wal_records()]
    assert len(seqs) >= 8
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_te97f91_u24_append_barrier_order() -> None:
    """WAL records release before clean before done for each scenario."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    for n in range(1, 4):
        steps = _wal_steps(n)
        assert steps.index("release") < steps.index("clean") < steps.index("done")


def test_te97f91_u25_report_phase_order() -> None:
    """Emitted rows follow sk8, fp3, sr5, xr4 order within each scenario."""
    _reset_workspace()
    _desk_run_in_order([0, 1, 2, 3])
    report = _emit_report()
    phase_order = {"sk8": 0, "fp3": 1, "sr5": 2, "xr4": 3}
    for scenario in range(4):
        subset = [r for r in report["rows"] if r["scenario"] == scenario]
        ranks = [phase_order[r["phase"]] for r in subset]
        assert ranks == sorted(ranks)


def test_te97f91_u26_checkpoint_seal_tracks_end() -> None:
    """Checkpoint wal_seq tracks the WAL tail after each invoke."""
    _reset_workspace()
    for n in range(4):
        _invoke_scenario(n)
        cp = _read_checkpoint()
        chain = _wal_records()
        assert cp["wal_seq"] == chain[-1]["seq"]
        assert cp["valid"] is True


def test_te97f91_u08_epoch_cache_replace() -> None:
    """Re-invoke replaces staging epoch-cache snapshot instead of accumulating ingest rows before export emit."""
    _reset_workspace()
    _invoke_scenario(1)
    expected_len = len(reference_epoch(1))
    subprocess.run([INVOKE, "--scenario", "1"], check=True)
    assert len(_epoch_rows(1)) == expected_len


def test_te97f91_u27_mount_slot_idempotent() -> None:
    """Second invoke leaves sr5 done row unchanged for scenario 1."""
    _reset_workspace()
    _invoke_scenario(1)
    first = _row_by_marker(_phase_rows(_epoch_rows(1), "sr5"), "done")
    subprocess.run([INVOKE, "--scenario", "1"], check=True)
    second = _row_by_marker(_phase_rows(_epoch_rows(1), "sr5"), "done")
    assert second == first


def test_te97f91_u09_isolated_index_two_rows() -> None:
    """Isolated scenario 2 epoch cache matches fixture-derived reference."""
    _reset_workspace()
    _invoke_scenario(2)
    assert _sort_rows(_epoch_rows(2)) == _sort_rows(reference_epoch(2))


def test_te97f91_u28_index_three_depth_listing() -> None:
    """Daemon scenario 3 xr4 listing includes a tail sector at least 512 (no mid 64)."""
    _reset_workspace()
    _invoke_scenario(3)
    sectors = {int(r["marker"].split("_", 1)[1]) for r in _phase_rows(_epoch_rows(3), "xr4")}
    assert any(sec >= 512 for sec in sectors)


def test_te97f91_u10_overlay_index_two_ledger() -> None:
    """Hidden s2 ledger overlay recomputes epoch rows from on-disk bytes."""
    dest = SEQ_ROOT / "s2" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(2)
        _reset_workspace()
        _invoke_scenario(2)
        assert _sort_rows(_epoch_rows(2)) == _sort_rows(reference_epoch(2, ledger_overlay=2))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u11_overlay_index_three_chain() -> None:
    """Hidden s3 ledger overlay recomputes full-chain digest."""
    dest = SEQ_ROOT / "s3" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(3)
        _reset_workspace()
        _desk_run_in_order([0, 1, 2, 3])
        report = _emit_report()
        assert report["chain_fingerprint"] == _chain_fingerprint(reference_full(3))
    finally:
        dest.write_bytes(backup)


def test_te97f91_u12_isolated_index_one_markers() -> None:
    """Index-one xr4 markers match reference under hidden ledger overlay."""
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _invoke_scenario(1)
        markers = {r["marker"] for r in _phase_rows(_epoch_rows(1), "xr4")}
        ref_markers = {r["marker"] for r in _phase_rows(reference_epoch(1, 1), "xr4")}
        assert markers == ref_markers
    finally:
        dest.write_bytes(backup)


def test_te97f91_u29_ledger_refresh_after_overlay() -> None:
    """Host ledger overlay refresh updates settle-driven sr5 rows on re-invoke."""
    _reset_workspace()
    _invoke_scenario(1)
    public_done = _row_by_marker(_phase_rows(_epoch_rows(1), "sr5"), "done")["sequence"]
    dest = SEQ_ROOT / "s1" / "b0.evt"
    backup = dest.read_bytes()
    try:
        _overlay_hidden_ledger(1)
        subprocess.run([INVOKE, "--scenario", "1"], check=True)
        overlay_done = _row_by_marker(_phase_rows(_epoch_rows(1), "sr5"), "done")["sequence"]
        ref_done = _row_by_marker(_phase_rows(reference_epoch(1, 1), "sr5"), "done")["sequence"]
        assert overlay_done == ref_done
        assert overlay_done != public_done
    finally:
        dest.write_bytes(backup)


def test_te97f91_u30_stacked_overlay_chain() -> None:
    """Stacked overlays on indices 1 and 3 produce multi-overlay full-chain digest."""
    backups = {n: (SEQ_ROOT / f"s{n}" / "b0.evt").read_bytes() for n in (1, 3)}
    try:
        _overlay_hidden_ledger(1)
        _reset_workspace()
        _desk_run_in_order([0, 1])
        _overlay_hidden_ledger(3)
        _desk_run_in_order([2, 3])
        report = _emit_report()
        expected = reference_full_multi(1, 3)
        assert report["chain_fingerprint"] == _chain_fingerprint(expected)
    finally:
        for n, blob in backups.items():
            (SEQ_ROOT / f"s{n}" / "b0.evt").write_bytes(blob)
