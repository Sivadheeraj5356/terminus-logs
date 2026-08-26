import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from ref_helpers import fn_load, fn_trace
from support import (
    assert_complete_trace,
    assert_engine_sources_unmodified,
    assert_fixture_unmodified,
)

APP = Path("/app")
OUT = APP / "output"
MANIFEST = APP / "environment" / "Cargo.toml"
# The verifier compiles the agent's sources into its own, non-agent-writable
# build directory and runs the binary it produced there. It never invokes the
# agent-owned build script and never runs /app/environment/bin/q7m, so a tampered
# script or a stale/planted binary cannot influence the result.
VERIFIER_BUILD = Path(tempfile.mkdtemp(prefix="q7m-verify-m1-"))
BIN = VERIFIER_BUILD / "release" / "q7m"
REPORT = OUT / "m1_mismatch_report.json"
FIXTURES = ["seq_r4.pgn", "seq_u8.pgn"]


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


def _gen_sequences() -> list[list[str]]:
    """Deterministic, non-fixture move lists so passing cannot rely on the three
    bundled fixture names alone. All moves start from a piece of the side to move,
    which both the engine and the reference apply identically."""
    return [
        ["g1f3", "g8f6", "f3g1", "f6g8"] * 3,
        ["e2e4", "e7e5"] + ["g1f3", "g8f6", "f3g1", "f6g8"] * 2,
        ["g1f3", "g8f6", "e2e4", "e7e5", "e1g1", "e8g8", "b1c3", "b8c6"],
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
    # Observation-only milestone: the engine must be the shipped one, so the
    # integrity pin runs before the verifier compiles anything.
    assert_engine_sources_unmodified()
    _build()


class TestK9ReplayObserve:
    def test_q7m_build_and_run_seq_r4(self):
        """q7m run-seq exits zero on seq_r4 per k9_rules.md."""
        assert _run_seq("seq_r4.pgn", OUT / "event_trace.jsonl")

    def test_seq_r4_trace_schema_matches_k9(self):
        """event_trace.jsonl rows contain ply, digest_hex, outcome_code per k9_rules.md."""
        rows = _run_seq("seq_r4.pgn", OUT / "event_trace.jsonl")
        for row in rows:
            assert set(row) >= {"ply", "digest_hex", "outcome_code"}
            assert len(row["digest_hex"]) == 16
            assert row["outcome_code"] in {"N", "H"}

    def test_engine_sources_unmodified(self):
        """Observation-only stage: every Rust source and manifest in the
        workspace still matches its shipped byte-level sha256 digest, and no extra
        Rust sources were added. A report generated from a modified engine
        cannot pass this milestone."""
        assert_engine_sources_unmodified()

    def test_fixtures_unmodified(self):
        """Bundled fixture scripts were not edited by the agent."""
        for fx in FIXTURES + ["seq_k2.pgn"]:
            assert_fixture_unmodified(fx)

    def test_pipeline_runs_on_generated_sequences(self):
        """The verifier-built engine replays non-fixture move lists and emits a
        complete, schema-valid trace, so the pipeline generalizes past the three
        bundled fixtures."""
        for moves in _gen_sequences():
            rows = _run_variant(moves)
            assert len(rows) == len(moves)
            for i, row in enumerate(rows, 1):
                assert row["ply"] == i
                assert set(row) >= {"ply", "digest_hex", "outcome_code"}
                assert len(row["digest_hex"]) == 16
                assert row["outcome_code"] in {"N", "H"}

    def test_mismatch_report_schema_valid(self):
        """m1_mismatch_report.json matches k9-mismatch-v1 schema."""
        doc = json.loads(REPORT.read_text())
        assert doc["schema"] == "k9-mismatch-v1"
        assert doc["fixtures"] == FIXTURES
        assert isinstance(doc["mismatches"], list)
        for row in doc["mismatches"]:
            assert set(row) >= {"fixture", "ply", "engine", "reference"}

    def test_mismatch_report_matches_reference_recompute(self):
        """m1_mismatch_report.json matches independently recomputed engine deltas."""
        doc = json.loads(REPORT.read_text())
        mismatches = []
        for fx in FIXTURES:
            ref = fn_trace(fn_load(fx))
            eng = _run_seq(fx, OUT / f"m1_{fx}.jsonl")
            for r, e in zip(ref, eng):
                if r[1] != e["outcome_code"]:
                    mismatches.append(
                        {
                            "fixture": fx,
                            "ply": r[0],
                            "engine": e["outcome_code"],
                            "reference": r[1],
                        }
                    )
        assert doc == {
            "schema": "k9-mismatch-v1",
            "fixtures": FIXTURES,
            "mismatches": mismatches,
        }

    def test_mismatch_report_lists_deltas(self):
        """m1_mismatch_report.json lists at least one engine vs reference delta."""
        doc = json.loads(REPORT.read_text())
        assert doc["mismatches"]

    def test_report_lists_seq_r4_deltas(self):
        """Mismatch report includes at least one seq_r4.pgn row."""
        doc = json.loads(REPORT.read_text())
        assert any(row["fixture"] == "seq_r4.pgn" for row in doc["mismatches"])

    def test_report_lists_seq_u8_deltas(self):
        """Mismatch report includes at least one seq_u8.pgn row."""
        doc = json.loads(REPORT.read_text())
        assert any(row["fixture"] == "seq_u8.pgn" for row in doc["mismatches"])

    def test_report_includes_overmarked_h(self):
        """Broken engine marks H where reference marks N on at least one ply."""
        doc = json.loads(REPORT.read_text())
        assert any(
            row["engine"] == "H" and row["reference"] == "N" for row in doc["mismatches"]
        )

    def test_report_includes_undermarked_h(self):
        """Broken engine marks N where reference marks H on at least one ply."""
        doc = json.loads(REPORT.read_text())
        assert any(
            row["engine"] == "N" and row["reference"] == "H" for row in doc["mismatches"]
        )

    def test_m1_regress_pipeline_mismatch_report(self):
        """Deleting the report and rerunning fixtures cannot pass with a static file.

        The report is regenerated from live engine output and restored to disk so
        the next milestone can consume it."""
        REPORT.unlink(missing_ok=True)
        mismatches = []
        for fx in FIXTURES:
            ref = fn_trace(fn_load(fx))
            eng = _run_seq(fx, OUT / f"chk_{fx}.jsonl")
            for r, e in zip(ref, eng):
                if r[1] != e["outcome_code"]:
                    mismatches.append(
                        {
                            "fixture": fx,
                            "ply": r[0],
                            "engine": e["outcome_code"],
                            "reference": r[1],
                        }
                    )
        assert mismatches, "broken engine should still produce mismatches"
        REPORT.write_text(
            json.dumps(
                {
                    "schema": "k9-mismatch-v1",
                    "fixtures": FIXTURES,
                    "mismatches": mismatches,
                },
                indent=2,
            )
            + "\n"
        )
