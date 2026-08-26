import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from ref_helpers import fn_load, fn_trace
from support import (
    assert_complete_trace,
    assert_fixture_unmodified,
    trace_path_for,
)

APP = Path("/app")
OUT = APP / "output"
MANIFEST = APP / "environment" / "Cargo.toml"
# Verifier-owned build directory: the verifier compiles the agent's sources here
# and runs the binary it produced, never the agent's build script or
# /app/environment/bin/q7m.
VERIFIER_BUILD = Path(tempfile.mkdtemp(prefix="q7m-verify-m2-"))
BIN = VERIFIER_BUILD / "release" / "q7m"
TRACE = trace_path_for("seq_r4.pgn")
M1_REPORT = OUT / "m1_mismatch_report.json"


def _build() -> None:
    shutil.rmtree(VERIFIER_BUILD, ignore_errors=True)
    proc = subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--offline",
            "--manifest-path",
            str(MANIFEST),
            "--target-dir",
            str(VERIFIER_BUILD),
        ],
        cwd="/app",
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert proc.returncode == 0 and BIN.exists(), proc.stderr + proc.stdout


def _run_bin(script: Path, out: Path) -> list[dict]:
    proc = subprocess.run(
        [str(BIN), "run-seq", "--script", str(script), "--out", str(out)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return [json.loads(line) for line in out.read_text().splitlines()]


def _run_seq(name: str, out: Path) -> list[dict]:
    assert_fixture_unmodified(name)
    rows = _run_bin(Path(f"/app/environment/fixtures/{name}"), out)
    assert_complete_trace(name, rows, len(fn_load(name)))
    return rows


def _compare_fixture(name: str) -> None:
    moves = fn_load(name)
    ref = fn_trace(moves)
    eng = _run_seq(name, trace_path_for(name))
    for r, e in zip(ref, eng):
        assert e["outcome_code"] == r[1], (
            f"{name} ply {r[0]}: engine {e['outcome_code']} != reference {r[1]}"
        )
        assert e["digest_hex"] == r[4], (
            f"{name} ply {r[0]}: engine digest_hex {e['digest_hex']} != reference {r[4]}"
        )


def _gen_sequences() -> list[list[str]]:
    """Deterministic, non-fixture move lists whose positions never recur, so the
    digest repair is exercised on inputs beyond the bundled fixtures. Because no
    position repeats, every ply is a non-claim on both sides; only the digest
    encoding (placement, side, castling rights, en-passant origin square) can
    differ, which is exactly what this milestone repairs."""
    return [
        ["g1f3", "g8f6", "b1c3", "b8c6"],
        ["e2e4", "e7e5", "g1f3", "g8f6", "f1c4", "f8c5", "e1g1", "e8g8"],
        ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4", "f3d4", "g8f6", "b1c3", "b8c6"],
    ]


def _run_variant(moves: list[str]) -> list[dict]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".pgn", dir=str(OUT), delete=False
    ) as fh:
        fh.write("\n".join(moves) + "\n")
        script = Path(fh.name)
    return _run_bin(script, Path(str(script) + ".jsonl"))


@pytest.fixture(scope="class", autouse=True)
def _built_binary():
    OUT.mkdir(parents=True, exist_ok=True)
    _build()


class TestMilestone2:
    def test_m1_report_artifact_present(self):
        """The milestone 1 mismatch report is present and well-formed before the
        repair is validated; this milestone builds on that recorded evidence."""
        assert M1_REPORT.exists(), "expected /app/output/m1_mismatch_report.json from milestone 1"
        doc = json.loads(M1_REPORT.read_text())
        assert doc["schema"] == "k9-mismatch-v1"
        assert doc["fixtures"] == ["seq_r4.pgn", "seq_u8.pgn"]
        assert isinstance(doc["mismatches"], list) and doc["mismatches"]
        for row in doc["mismatches"]:
            assert set(row) >= {"fixture", "ply", "engine", "reference"}

    def test_q7m_build_and_run_seq_r4(self):
        """q7m run-seq exits zero on seq_r4 per k9_rules.md."""
        assert _run_seq("seq_r4.pgn", TRACE)

    def test_event_trace_schema_matches_k9(self):
        """event_trace.jsonl rows match k9_rules.md trace schema."""
        rows = _run_seq("seq_r4.pgn", TRACE)
        for row in rows:
            assert set(row) >= {"ply", "digest_hex", "outcome_code"}
            assert len(row["digest_hex"]) == 16
            assert row["outcome_code"] in {"N", "H"}

    def test_seq_r4_outcome_matches_reference_every_ply(self):
        """seq_r4 outcome_code and digest_hex match reference on every ply."""
        _compare_fixture("seq_r4.pgn")

    def test_seq_r4_late_band_matches_reference(self):
        """seq_r4 plies 14-17 match reference outcome_code and digest_hex."""
        moves = fn_load("seq_r4.pgn")
        ref = fn_trace(moves)
        eng = _run_seq("seq_r4.pgn", TRACE)
        for r, e in zip(ref[13:17], eng[13:17]):
            assert e["outcome_code"] == r[1], (
                f"ply {r[0]}: engine {e['outcome_code']} != reference {r[1]}"
            )
            assert e["digest_hex"] == r[4], (
                f"ply {r[0]}: engine digest_hex {e['digest_hex']} != reference {r[4]}"
            )

    def test_generated_sequences_digest_matches_reference(self):
        """Non-fixture, non-repeating move lists match the reference digest_hex on
        every ply, so the digest repair generalizes past the bundled fixtures."""
        for moves in _gen_sequences():
            ref = fn_trace(moves)
            eng = _run_variant(moves)
            assert len(eng) == len(ref)
            for r, e in zip(ref, eng):
                assert e["digest_hex"] == r[4], (
                    f"ply {r[0]}: engine digest_hex {e['digest_hex']} != reference {r[4]}"
                )
                assert e["outcome_code"] == r[1], (
                    f"ply {r[0]}: engine {e['outcome_code']} != reference {r[1]}"
                )

    def test_m2_regress_pipeline_event_trace(self):
        """event_trace.jsonl must come from a live run, not a static partial file."""
        TRACE.unlink(missing_ok=True)
        first = _run_seq("seq_r4.pgn", TRACE)
        TRACE.unlink(missing_ok=True)
        second = _run_seq("seq_r4.pgn", TRACE)
        assert first == second
