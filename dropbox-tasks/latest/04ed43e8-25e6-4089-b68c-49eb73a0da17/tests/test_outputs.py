"""state-audit coordination trace verifier — contract-derived expectations."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

TRACE_PATH = Path("/app/output/coordination_trace.json")
WORKSPACE = Path("/app/data/workspace")
FIXTURES = Path("/app/environment/fixtures/cycle")
ENV_ROOT = Path("/app/environment")
BIN_PATH = Path("/app/bin/state-audit")
MATRIX_ROWS = [
    "slice_once",
    "slice_twice",
    "recycle_trap",
    "warm_resume",
    "staggered_width",
]


def _sha16(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode()
    proc = subprocess.run(
        ["sha256sum"],
        input=payload,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().split()[0][:16]


def _marker_fp(label: str, body: bytes) -> str:
    return _sha16(f"{label}|".encode() + body)


def _preservation_stamp(gen: int, fixture_body: bytes) -> str:
    return _sha16(f"{gen}|".encode() + fixture_body)


def _lineage_token(parent_gen: int, journal_body: bytes, latch_body: bytes) -> str:
    return _sha16(f"{parent_gen}|".encode() + journal_body + latch_body)


def _row_seal(row: dict[str, Any]) -> str:
    canonical = "|".join(
        [
            str(row["scenario"]),
            str(row["slice_epoch"]),
            str(row["marker_fp_host"]),
            str(row["marker_fp_peer"]),
            str(row["hold_gap"]),
            str(row["staging_lag"]),
            str(row["checkpoint_epoch"]),
            str(row["lineage_token"]),
            str(row["preservation_stamp"]),
        ]
    )
    return _sha16(canonical)


def _report_digest(rows: list[dict[str, Any]]) -> str:
    fragments: list[str] = []
    for row in rows:
        fragments.append(
            ";".join(
                [
                    str(row["scenario"]),
                    str(row["slice_epoch"]),
                    str(row["marker_fp_host"]),
                    str(row["marker_fp_peer"]),
                    str(row["hold_gap"]),
                    str(row["staging_lag"]),
                    str(row["checkpoint_epoch"]),
                    str(row["lineage_token"]),
                    str(row["preservation_stamp"]),
                    str(row["row_seal"]),
                ]
            )
        )
    joined = "\n".join(sorted(fragments))
    return _sha16(joined)


def _replay_token(report_digest: str, workspace: str) -> str:
    return _sha16(f"{report_digest}|{workspace}")


def _fixture_body(gen: int) -> bytes:
    return (FIXTURES / f"gen{gen}" / "workspace.dat").read_bytes()


def _journal_body() -> bytes:
    path = WORKSPACE / "journal" / "committed.log"
    if not path.exists():
        return b""
    return path.read_bytes()


def _latch_body() -> bytes:
    path = WORKSPACE / "gate" / "latch"
    if not path.exists():
        return b""
    return path.read_bytes()


def _staging_lag() -> int:
    staging = WORKSPACE / "journal" / "staging.log"
    cursor = WORKSPACE / "journal" / "cursor"
    if not staging.exists():
        return 0
    body = staging.read_bytes()
    if not cursor.exists():
        return len(body)
    cur = int(cursor.read_text(encoding="utf-8").strip() or "0")
    return len(body) - cur


def _build_state_audit() -> None:
    subprocess.run(
        ["go", "build", "-o", "/app/bin/state-audit", "./driver/"],
        cwd=ENV_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_state_audit() -> dict[str, Any]:
    if TRACE_PATH.exists():
        TRACE_PATH.unlink()
    subprocess.run(
        [
            "/app/bin/state-audit",
            "--trace",
            "/app/output/coordination_trace.json",
            "--workspace",
            "/app/data/workspace",
            "--fixtures",
            "/app/environment/fixtures/cycle",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(TRACE_PATH.read_text(encoding="utf-8"))


def _row(doc: dict[str, Any], name: str) -> dict[str, Any]:
    for run in doc.get("runs") or []:
        if run.get("scenario") == name:
            return run
    raise AssertionError(f"missing matrix row {name}")


def _wipe_workspace() -> None:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    subprocess.run(
        [
            "bash",
            "/app/environment/scripts/setup_workspace.sh",
            "/app/data/workspace",
            "/app/environment/fixtures/cycle",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def audit_doc() -> dict[str, Any]:
    _build_state_audit()
    _wipe_workspace()
    return _run_state_audit()


def test_sa01_fresh_shape(audit_doc: dict[str, Any]) -> None:
    """Baseline runs array and global fields after first audit."""
    assert isinstance(audit_doc.get("runs"), list)
    assert len(audit_doc["runs"]) == len(MATRIX_ROWS)
    names = {row["scenario"] for row in audit_doc["runs"]}
    assert names == set(MATRIX_ROWS)
    for key in ("report_digest", "replay_token"):
        val = audit_doc.get(key)
        assert isinstance(val, str) and len(val) == 16
    for row in audit_doc["runs"]:
        for field in (
            "scenario",
            "slice_epoch",
            "marker_fp_host",
            "marker_fp_peer",
            "hold_gap",
            "staging_lag",
            "checkpoint_epoch",
            "lineage_token",
            "preservation_stamp",
            "row_seal",
        ):
            assert field in row


def test_sa02_dual_run_envelope_stable(audit_doc: dict[str, Any]) -> None:
    """Identical report_digest and replay_token across consecutive audits."""
    first_digest = audit_doc["report_digest"]
    first_token = audit_doc["replay_token"]
    second = _run_state_audit()
    assert second["report_digest"] == first_digest
    assert second["replay_token"] == first_token


def test_sa03_hold_gap_zero(audit_doc: dict[str, Any]) -> None:
    """Coordinated repair drives hold_gap to zero for every matrix row."""
    for name in MATRIX_ROWS:
        row = _row(audit_doc, name)
        assert row["hold_gap"] == 0, f"{name} hold_gap={row['hold_gap']}"


def test_sa04_staging_lag_zero(audit_doc: dict[str, Any]) -> None:
    """Journal flush leaves no staging tail lag after repair."""
    for name in MATRIX_ROWS:
        row = _row(audit_doc, name)
        assert row["staging_lag"] == 0, f"{name} staging_lag={row['staging_lag']}"


def test_sa05_checkpoint_epoch_align(audit_doc: dict[str, Any]) -> None:
    """Published checkpoint sidecar matches slice_epoch on every row."""
    for name in MATRIX_ROWS:
        row = _row(audit_doc, name)
        assert row["checkpoint_epoch"] == row["slice_epoch"], name


def test_sa06_dual_fp_split(audit_doc: dict[str, Any]) -> None:
    """Host and peer fingerprints agree when authorities are aligned."""
    for name in MATRIX_ROWS:
        row = _row(audit_doc, name)
        host_fp = _marker_fp("host", _fixture_body(row["slice_epoch"]))
        peer_fp = _marker_fp("peer", _fixture_body(row["slice_epoch"]))
        assert row["marker_fp_host"] == host_fp
        assert row["marker_fp_peer"] == peer_fp


def test_sa07_warm_resume_delayed_clear(audit_doc: dict[str, Any]) -> None:
    """Warm-resume row reaches epoch 2 with zero lag after coordinated repair."""
    row = _row(audit_doc, "warm_resume")
    assert row["slice_epoch"] == 2
    assert row["staging_lag"] == 0
    assert row["hold_gap"] == 0


def test_sa08_repeat_cycle_drift(audit_doc: dict[str, Any]) -> None:
    """Second replay slice stays aligned in slice_twice matrix row."""
    row = _row(audit_doc, "slice_twice")
    assert row["slice_epoch"] == 2
    assert row["hold_gap"] == 0
    stamp = _preservation_stamp(2, _fixture_body(2))
    assert row["preservation_stamp"] == stamp


def test_sa09_fixture_binding(audit_doc: dict[str, Any]) -> None:
    """preservation_stamp matches sha256 prefix of archived fixture body."""
    for name in MATRIX_ROWS:
        row = _row(audit_doc, name)
        gen = int(row["slice_epoch"])
        expected = _preservation_stamp(gen, _fixture_body(gen))
        assert row["preservation_stamp"] == expected, name


def test_sa10_lineage_stable_across_reruns(audit_doc: dict[str, Any]) -> None:
    """lineage_token for recycle_trap is stable across consecutive replays."""
    row1 = _row(audit_doc, "recycle_trap")
    doc2 = _run_state_audit()
    row2 = _row(doc2, "recycle_trap")
    assert row1["lineage_token"] == row2["lineage_token"]
    assert len(row1["lineage_token"]) == 16


def test_sa11_regen_required() -> None:
    """Rebuild blocks static output file."""
    _wipe_workspace()
    fake = {
        "runs": [],
        "report_digest": "0" * 16,
        "replay_token": "0" * 16,
    }
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text(json.dumps(fake), encoding="utf-8")
    if BIN_PATH.exists():
        BIN_PATH.unlink()
    _build_state_audit()
    doc = _run_state_audit()
    assert doc["runs"], "state-audit must regenerate non-empty runs"
    assert doc["report_digest"] != fake["report_digest"]


def test_sa12_envelope_crosscheck(audit_doc: dict[str, Any]) -> None:
    """report_digest matches recomputed canonical envelope."""
    rows = audit_doc["runs"]
    sealed_rows: list[dict[str, Any]] = []
    for row in rows:
        sealed = dict(row)
        sealed["row_seal"] = _row_seal(sealed)
        sealed_rows.append(sealed)
    expected_digest = _report_digest(sealed_rows)
    assert audit_doc["report_digest"] == expected_digest
    expected_token = _replay_token(expected_digest, str(WORKSPACE))
    assert audit_doc["replay_token"] == expected_token


def test_sa13_staggered_parallel_order(audit_doc: dict[str, Any]) -> None:
    """Wide parallel bring-up row stays aligned after gate/journal ordering."""
    row = _row(audit_doc, "staggered_width")
    assert row["slice_epoch"] == 2
    assert row["staging_lag"] == 0
    assert row["checkpoint_epoch"] == 2
