"""Domain verifier for the duel rollback engine."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
REPORT = OUT / "duel_report.json"
DUEL = str(ENV / "bin" / "duel")
BUILD = ["bash", str(ENV / "scripts" / "build_all.sh")]
REF = ["python3", str(Path("/tests") / "duel_ref.py")]

TAPES = ["warmup", "clash", "zoning", "pressure", "endgame", "flush_edge"]


def _build():
    subprocess.run(BUILD, check=True)


def _run_report():
    _build()
    return subprocess.run([DUEL], capture_output=True, text=True).returncode


def _load_report():
    assert REPORT.is_file(), "duel_report.json missing"
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    return {row["tape_id"]: row for row in data["rows"]}


def _load_tape(name):
    return json.loads((ENV / "tapes" / (name + ".json")).read_text(encoding="utf-8"))


def _ref(tape):
    proc = subprocess.run(
        REF + ["--tape-json", json.dumps(tape)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip())


def _probe(tape):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(tape, fh)
        path = fh.name
    proc = subprocess.run([DUEL, "--tape-file", path], capture_output=True, text=True)
    return json.loads(proc.stdout.strip())


@pytest.fixture(scope="module", autouse=True)
def _ensure_report():
    code = _run_report()
    assert code == 0, "duel report run must exit 0 (all tapes converged)"


def test_report_has_all_tapes():
    report = _load_report()
    for name in TAPES:
        assert name in report, "missing tape row: " + name


def test_all_tapes_converge():
    report = _load_report()
    for name in TAPES:
        row = report[name]
        assert row["converged"] is True, name + " did not converge"
        assert row["confirmed_digest"] == row["host_digest"]


def test_host_rules_match_reference():
    report = _load_report()
    for name in TAPES:
        want = _ref(_load_tape(name))
        assert report[name]["host_digest"] == want["host_digest"], name


def test_client_prediction_matches_reference():
    report = _load_report()
    for name in TAPES:
        want = _ref(_load_tape(name))
        assert report[name]["pred_digest"] == want["pred_digest"], name


def test_rollbacks_match_reference():
    report = _load_report()
    for name in TAPES:
        want = _ref(_load_tape(name))
        row = report[name]
        assert row["rollbacks"] == want["rollbacks"], name
        assert row["rollbacks"] > 0, name


def test_final_hp_matches_reference():
    report = _load_report()
    for name in TAPES:
        want = _ref(_load_tape(name))
        assert report[name]["final_hp"] == want["final_hp"], name


def test_prediction_differs_from_host_under_rollback():
    report = _load_report()
    for name in ["clash", "zoning", "endgame", "flush_edge"]:
        row = report[name]
        assert row["pred_digest"] != row["host_digest"], name


def test_flush_edge_requires_tail_frames():
    row = _load_report()["flush_edge"]
    tape = _load_tape("flush_edge")
    assert row["delay"] == tape["delay"]
    assert row["ticks"] == len(tape["inputs"])
    assert row["rollbacks"] > 0


def test_delay_ladder_generalizes():
    base = [[2, 1], [2, 1], [4, 4], [4, 8], [4, 4], [16, 4], [4, 4], [4, 8]]
    for delay in (1, 2, 3, 4, 5):
        tape = {"tape_id": "lad_" + str(delay), "delay": delay, "inputs": base}
        row = _probe(tape)
        want = _ref(tape)
        assert row["converged"] is True
        assert row["host_digest"] == want["host_digest"]
        assert row["pred_digest"] == want["pred_digest"]
        assert row["rollbacks"] == want["rollbacks"]


def test_repeat_remote_policy_required():
    tape = {
        "tape_id": "policy_probe",
        "delay": 1,
        "inputs": [[4, 4], [4, 8], [4, 4], [8, 4], [4, 4], [16, 4], [4, 4]],
    }
    row = _probe(tape)
    want = _ref(tape)
    assert row["pred_digest"] == want["pred_digest"]
    assert row["rollbacks"] == want["rollbacks"]
    assert row["converged"] is True


def test_probe_high_latency_generalizes():
    tape = {
        "tape_id": "probe_hi",
        "delay": 6,
        "inputs": [
            [2, 1], [2, 1], [4, 4], [4, 8], [4, 4], [8, 4], [4, 4], [16, 8],
            [4, 4], [4, 4], [4, 8], [4, 4], [16, 4], [4, 4], [4, 8], [4, 4],
        ],
    }
    row = _probe(tape)
    want = _ref(tape)
    assert row["converged"] is True
    assert row["host_digest"] == want["host_digest"]
    assert row["pred_digest"] == want["pred_digest"]
    assert row["confirmed_digest"] == want["host_digest"]
    assert row["rollbacks"] == want["rollbacks"]


def test_report_deterministic_across_rebuilds():
    _build()
    first = _load_report()
    _build()
    subprocess.run([DUEL], capture_output=True, text=True, check=True)
    second = _load_report()
    for name in TAPES:
        assert first[name]["confirmed_digest"] == second[name]["confirmed_digest"]
        assert first[name]["pred_digest"] == second[name]["pred_digest"]
