import json
import random
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
VERIFIER_BUILD = Path(tempfile.mkdtemp(prefix="q7m-verify-m3-"))
BIN = VERIFIER_BUILD / "release" / "q7m"
TRACE_R4 = trace_path_for("seq_r4.pgn")
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
            f"{name} ply {r[0]}: digest {e['digest_hex']} != reference {r[4]}"
        )


def _gen_sequences() -> list[list[str]]:
    """Deterministic, non-fixture move lists that force position repetition,
    en-passant origin squares, and castling-file king moves so the repaired
    repetition counter and digest are validated on inputs beyond the bundled
    fixtures. The engine and the reference apply every move identically, so a
    correct repair must agree on outcome_code and digest_hex on all of them."""
    seqs = [
        ["g1f3", "g8f6", "f3g1", "f6g8"] * 3,
        ["b1c3", "b8c6", "c3b1", "c6b8"] * 3,
        ["e2e4", "e7e5", "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8"],
        ["g1f3", "g8f6", "e1g1", "e8g8", "g1f1", "g8f8", "f1g1", "f8g8", "g1f1", "g8f8"],
    ]
    for seed in (3, 11, 29):
        rng = random.Random(seed)
        seq: list[str] = []
        for _ in range(5):
            w = rng.choice([["g1f3", "f3g1"], ["b1c3", "c3b1"]])
            b = rng.choice([["g8f6", "f6g8"], ["b8c6", "c6b8"]])
            seq += [w[0], b[0], w[1], b[1]]
        seqs.append(seq)
    return seqs


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


class TestMilestone3:
    def test_prior_milestone_artifacts_present(self):
        """The milestone 1 report and the milestone 2 seq_r4 trace produced by the
        earlier stages are present before the final repair is validated."""
        assert M1_REPORT.exists(), "expected /app/output/m1_mismatch_report.json from milestone 1"
        doc = json.loads(M1_REPORT.read_text())
        assert doc["schema"] == "k9-mismatch-v1"
        assert isinstance(doc["mismatches"], list) and doc["mismatches"]
        assert TRACE_R4.exists(), "expected /app/output/event_trace.jsonl from milestone 2"

    def test_q7m_build_and_run_seq_r4(self):
        """q7m run-seq exits zero on seq_r4 per k9_rules.md."""
        assert _run_seq("seq_r4.pgn", TRACE_R4)

    def test_u8_trace_schema_matches_k9(self):
        """u8.jsonl rows match k9_rules.md trace schema."""
        rows = _run_seq("seq_u8.pgn", trace_path_for("seq_u8.pgn"))
        for row in rows:
            assert set(row) >= {"ply", "digest_hex", "outcome_code"}
            assert len(row["digest_hex"]) == 16

    def test_seq_r4_regress_still_matches_reference(self):
        """seq_r4 remains aligned with the reference adjudicator."""
        moves = fn_load("seq_r4.pgn")
        ref = fn_trace(moves)
        eng = _run_seq("seq_r4.pgn", TRACE_R4)
        for r, e in zip(ref, eng):
            assert e["outcome_code"] == r[1]
            assert e["digest_hex"] == r[4]

    def test_seq_u8_outcome_matches_reference_every_ply(self):
        """seq_u8 outcome_code and digest_hex match reference on every ply."""
        _compare_fixture("seq_u8.pgn")

    def test_seq_u8_first_h_matches_reference(self):
        """seq_u8 first reference H row matches engine outcome_code and digest_hex."""
        ref = fn_trace(fn_load("seq_u8.pgn"))
        h_idx = next(i for i, r in enumerate(ref) if r[1] == "H")
        eng = _run_seq("seq_u8.pgn", trace_path_for("seq_u8.pgn"))
        assert eng[h_idx]["outcome_code"] == "H"
        assert eng[h_idx]["digest_hex"] == ref[h_idx][4]

    def test_seq_k2_outcome_matches_reference_every_ply(self):
        """seq_k2 outcome_code and digest_hex match reference on every ply."""
        _compare_fixture("seq_k2.pgn")

    def test_seq_k2_first_h_matches_reference(self):
        """seq_k2 first reference H row matches engine outcome_code and digest_hex."""
        ref = fn_trace(fn_load("seq_k2.pgn"))
        h_idx = next(i for i, r in enumerate(ref) if r[1] == "H")
        eng = _run_seq("seq_k2.pgn", trace_path_for("seq_k2.pgn"))
        assert eng[h_idx]["outcome_code"] == "H"
        assert eng[h_idx]["digest_hex"] == ref[h_idx][4]

    def test_seq_k2_aux_slot_varies_across_plies(self):
        """seq_k2 reference trace uses more than one aux slot value."""
        moves = fn_load("seq_k2.pgn")
        ref = fn_trace(moves)
        assert len({row[3] for row in ref}) > 1
        eng = _run_seq("seq_k2.pgn", trace_path_for("seq_k2.pgn"))
        for r, e in zip(ref, eng):
            assert e["outcome_code"] == r[1]
            assert e["digest_hex"] == r[4]

    def test_generated_sequences_match_reference_every_ply(self):
        """Non-fixture move lists that repeat positions and use en-passant and
        castling-file king moves match the reference on outcome_code and
        digest_hex on every ply, so the repair generalizes past the fixtures."""
        for moves in _gen_sequences():
            ref = fn_trace(moves)
            eng = _run_variant(moves)
            assert len(eng) == len(ref)
            for r, e in zip(ref, eng):
                assert e["outcome_code"] == r[1], (
                    f"ply {r[0]}: engine {e['outcome_code']} != reference {r[1]}"
                )
                assert e["digest_hex"] == r[4], (
                    f"ply {r[0]}: engine digest_hex {e['digest_hex']} != reference {r[4]}"
                )

    def test_required_output_files_exist(self):
        """All milestone 3 required trace files exist on disk."""
        for path in (
            TRACE_R4,
            trace_path_for("seq_u8.pgn"),
            trace_path_for("seq_k2.pgn"),
        ):
            assert path.exists(), f"missing required output {path}"

    def test_m3_regress_pipeline_all_traces(self):
        """Deleting outputs and rerunning cannot pass with static partial traces."""
        paths = [
            TRACE_R4,
            trace_path_for("seq_u8.pgn"),
            trace_path_for("seq_k2.pgn"),
        ]
        for path in paths:
            path.unlink(missing_ok=True)
        for fx in ("seq_r4.pgn", "seq_u8.pgn", "seq_k2.pgn"):
            _run_seq(fx, trace_path_for(fx))
