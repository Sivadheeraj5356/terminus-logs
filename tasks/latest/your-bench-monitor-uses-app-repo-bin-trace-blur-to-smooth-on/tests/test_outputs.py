import json
import math
import subprocess
import tempfile
from pathlib import Path

ROOT = Path("/app/repo")
BIN = ROOT / "bin" / "trace_blur"


def _run(cmd, payload):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payload, fh)
        path = fh.name
    proc = subprocess.run(cmd + [path], text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)


def _compare(actual, expected):
    assert len(actual["results"]) == len(expected["results"])
    for got, want in zip(actual["results"], expected["results"]):
        assert len(got["filtered"]) == len(want["filtered"])
        for gv, wv in zip(got["filtered"], want["filtered"]):
            assert math.isclose(gv, wv, rel_tol=1e-7, abs_tol=1e-7)


def test_visible_sample_matches_reference():
    payload = json.loads((ROOT / "samples" / "requests.json").read_text())
    expected = json.loads(Path("/tests/reference/expected_visible.json").read_text())
    _compare(_run([str(BIN)], payload), expected)


def test_manual_regressions_match_reference():
    payload = json.loads(Path("/tests/reference/manual_cases.json").read_text())
    expected = json.loads(Path("/tests/reference/expected_manual.json").read_text())
    _compare(_run([str(BIN)], payload), expected)


def test_generated_corpus_matches_reference():
    payload = json.loads(Path("/tests/reference/generated_cases.json").read_text())
    expected = json.loads(Path("/tests/reference/generated_expected.json").read_text())
    _compare(_run([str(BIN)], payload), expected)


def test_invalid_requests_are_rejected():
    cases = [
        {"inputs": [{"signal": [], "sigma": 1.0}]},
        {"inputs": [{"signal": [1.0], "sigma": 0.0}]},
        {"inputs": [{"signal": [1.0], "sigma": 1.0, "mode": "mirror"}]},
        {"inputs": [{"signal": [1.0], "sigma": 1.0, "mode": ""}]},
        {"inputs": [{"signal": [1.0], "sigma": 1.0, "truncate": 0.0}]},
    ]
    for payload in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh)
            path = fh.name
        proc = subprocess.run([str(BIN), path], text=True, capture_output=True)
        assert proc.returncode != 0
