"""Verifier for dye-transfer continuum desk."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
BIN = Path("/app/bin")
CASES = ENV / "data" / "cases"
DENSCORE = BIN / "denscore"
CINECONT = BIN / "cinecont"

T0, H0, BETA = 20.0, 50.0, 0.012
ALPHA = {"cyan": 0.0021, "magenta": 0.0018, "yellow": 0.0024, "silver": 0.0010}
CHANNELS = ["cyan", "magenta", "yellow", "silver"]
EPS = 1e-9
THR = 0.035


def _corr(d_raw: float, ch: str, temp_c: float, rh_pct: float) -> float:
    return d_raw * math.exp(ALPHA[ch] * (temp_c - T0)) * (1.0 + BETA * (rh_pct - H0) / 100.0)


def _interp(samples: list[dict], pos: float) -> dict[str, float]:
    if not samples:
        return {c: 0.0 for c in CHANNELS}
    if len(samples) == 1:
        s = samples[0]
        return {c: s[c] for c in CHANNELS}
    left = right = samples[0]
    for a, b in zip(samples, samples[1:]):
        if a["pos"] <= pos <= b["pos"]:
            left, right = a, b
            break
    if right["pos"] == left["pos"]:
        t = 0.0
    else:
        t = (pos - left["pos"]) / (right["pos"] - left["pos"])
    return {c: left[c] + t * (right[c] - left[c]) for c in CHANNELS}


def oracle_reel_dens(samples: list[dict], temp_c: float, rh_pct: float) -> dict:
    corrected = []
    for s in samples:
        corrected.append(
            {
                "pos": s["pos"],
                **{c: _corr(s[c], c, temp_c, rh_pct) for c in CHANNELS},
            }
        )
    mids = [s for s in corrected if 0.40 <= s["pos"] <= 0.60] or corrected
    mid = {c: sum(s[c] for s in mids) / len(mids) for c in CHANNELS}
    return {
        "start": _interp(corrected, 0.0),
        "end": _interp(corrected, 1.0),
        "mid": mid,
    }


def oracle_gap(end_a: dict, mid_a: dict, start_b: dict, mid_b: dict) -> dict[str, float]:
    out = {}
    for c in CHANNELS:
        out[c] = math.log10(max(end_a[c], EPS) / max(mid_a[c], EPS)) - math.log10(
            max(start_b[c], EPS) / max(mid_b[c], EPS)
        )
    return out


def round6(v: float) -> float:
    return round(v, 6)


def json_gap(v: float):
    r = round6(v)
    if abs(r - round(r)) < 1e-12:
        return int(round(r))
    return r


def oracle_output_digest(splices: list[dict]) -> str:
    rows = []
    for sp in sorted(splices, key=lambda x: x["splice_id"]):
        gaps = sp["gaps"]
        rows.append(
            {
                "splice_id": sp["splice_id"],
                "gaps": {c: json_gap(gaps[c]) for c in CHANNELS},
            }
        )
    raw = json.dumps(rows, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def rebuild_binaries() -> None:
    subprocess.run(
        [
            "bash",
            "-c",
            "cd /app/environment && cargo build --release --offline && cp target/release/denscore /app/bin/denscore",
        ],
        check=True,
        timeout=420,
    )
    subprocess.run(
        ["bash", "-c", "cd /app/environment && go build -o /app/bin/cinecont ./cmd/cinecont"],
        check=True,
        timeout=180,
    )


def run_case(case_path: Path, out_dir: Path) -> subprocess.CompletedProcess:
    out_dir.mkdir(parents=True, exist_ok=True)
    cine = (BIN / "cinecont").as_posix()
    return subprocess.run(
        [cine, "run", "--case", case_path.as_posix(), "--out", out_dir.as_posix()],
        capture_output=True,
        text=True,
        timeout=120,
    )


def load_report(out_dir: Path) -> dict:
    return json.loads((out_dir / "continuum_report.json").read_text())


def oracle_case(case: dict) -> dict:
    temp_c = case["temp_c"]
    rh_pct = case["rh_pct"]
    thr = case.get("threshold", THR) or THR
    reel_d = {}
    for reel in case["reels"]:
        reel_d[reel["reel_id"]] = oracle_reel_dens(reel["samples"], temp_c, rh_pct)
    splices = []
    all_ok = True
    for sp in sorted(case["splices"], key=lambda x: x["splice_id"]):
        a = reel_d[sp["reel_a"]]
        b = reel_d[sp["reel_b"]]
        gaps = oracle_gap(a["end"], a["mid"], b["start"], b["mid"])
        ok = all(abs(gaps[c]) <= thr for c in CHANNELS)
        all_ok = all_ok and ok
        splices.append({"splice_id": sp["splice_id"], "gaps": gaps, "ok": ok})
    return {
        "continuum_verdict": "pass" if all_ok else "fail",
        "splices": splices,
        "output_digest": oracle_output_digest(splices),
    }


@pytest.fixture(scope="session", autouse=True)
def _rebuild_once():
    rebuild_binaries()


@pytest.fixture
def fresh_out(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    return out


def test_rebuild_binaries_exist():
    """built binaries are present after rebuild."""
    assert DENSCORE.is_file()
    assert CINECONT.is_file()


def test_pass_case_verdict_and_digest_consistency(fresh_out):
    """Passing case matches oracle verdict and cross-artifact digests."""
    case_path = CASES / "festival-continuum-pass.json"
    case = json.loads(case_path.read_text())
    proc = run_case(case_path, fresh_out)
    assert proc.returncode == 0, proc.stderr
    report = load_report(fresh_out)
    expected = oracle_case(case)
    assert report["continuum_verdict"] == "pass"
    assert report["continuum_verdict"] == expected["continuum_verdict"]
    assert report["output_digest"] == expected["output_digest"]
    log = (fresh_out / "continuum_summary.log").read_text()
    assert "VERDICT=pass" in log
    assert f"DIGEST={report['output_digest']}" in log
    state = json.loads((fresh_out / "continuum_state.json").read_text())
    assert state["last_output_digest"] == report["output_digest"]


def test_fail_case_gaps_exceed_threshold(fresh_out):
    """Failing splice chain reports fail with oracle-matching gaps."""
    case_path = CASES / "festival-continuum-fail.json"
    case = json.loads(case_path.read_text())
    proc = run_case(case_path, fresh_out)
    assert proc.returncode == 0
    report = load_report(fresh_out)
    expected = oracle_case(case)
    assert report["continuum_verdict"] == "fail"
    assert report["output_digest"] == expected["output_digest"]
    for got, exp in zip(report["splices"], expected["splices"]):
        assert got["ok"] is False
        for c in CHANNELS:
            assert got["gaps"][c] == pytest.approx(exp["gaps"][c], rel=1e-6, abs=1e-6)
            assert abs(got["gaps"][c]) > THR


def test_climate_mutation_changes_digest_and_epoch(fresh_out):
    """Climate change recomputes densities, bumps epoch, and refreshes cache digest."""
    case_path = CASES / "festival-continuum-climate.json"
    case = json.loads(case_path.read_text())
    proc1 = run_case(case_path, fresh_out)
    assert proc1.returncode == 0
    r1 = load_report(fresh_out)
    s1 = json.loads((fresh_out / "continuum_state.json").read_text())
    case_hot = dict(case)
    case_hot["temp_c"] = 28.0
    case_hot["rh_pct"] = 72.0
    hot_path = fresh_out / "climate-hot.json"
    hot_path.write_text(json.dumps(case_hot))
    proc2 = run_case(hot_path, fresh_out)
    assert proc2.returncode == 0
    r2 = load_report(fresh_out)
    s2 = json.loads((fresh_out / "continuum_state.json").read_text())
    assert s2["epoch"] == s1["epoch"] + 1
    exp_hot = oracle_case(case_hot)
    assert r2["output_digest"] == exp_hot["output_digest"]
    assert r2["denscore_digest"] != r1["denscore_digest"]
    assert s2["cache_digest"] != s1["cache_digest"]


def test_cross_artifact_digest_agreement(fresh_out):
    """Report, summary log, state, history, and ledger agree on digests."""
    case_path = CASES / "festival-continuum-pass.json"
    case = json.loads(case_path.read_text())
    proc = run_case(case_path, fresh_out)
    assert proc.returncode == 0
    report = load_report(fresh_out)
    expected = oracle_case(case)
    assert report["output_digest"] == expected["output_digest"]
    digest = report["output_digest"]
    log = (fresh_out / "continuum_summary.log").read_text()
    assert f"DIGEST={digest}" in log
    state = json.loads((fresh_out / "continuum_state.json").read_text())
    assert state["last_output_digest"] == digest
    hist_lines = (fresh_out / "continuum_history.jsonl").read_text().strip().splitlines()
    last = json.loads(hist_lines[-1])
    assert last["output_digest"] == digest
    ledger = json.loads((fresh_out / "continuum_run_ledger.json").read_text())
    assert ledger["runs"][-1]["output_digest"] == digest
    assert ledger["runs"][-1]["denscore_digest"] == report["denscore_digest"]


def test_invalid_input_cleanup(fresh_out):
    """Invalid case stderr prefix and no continuum_report.json created."""
    bad = CASES / "invalid-empty.json"
    proc = run_case(bad, fresh_out)
    assert proc.returncode != 0
    assert proc.stderr.startswith("invalid continuum case input:")
    assert not (fresh_out / "continuum_report.json").exists()


def test_rho_cli_subprocess_oracle():
    """rho CLI stdin/stdout matches independent climate and midtone oracle."""
    payload = {
        "temp_c": 23.5,
        "rh_pct": 62.0,
        "samples": [
            {"pos": 0.0, "cyan": 0.40, "magenta": 0.35, "yellow": 0.30, "silver": 0.20},
            {"pos": 0.25, "cyan": 0.90, "magenta": 0.20, "yellow": 0.70, "silver": 0.10},
            {"pos": 0.5, "cyan": 0.50, "magenta": 0.45, "yellow": 0.40, "silver": 0.25},
            {"pos": 0.75, "cyan": 0.70, "magenta": 0.30, "yellow": 0.20, "silver": 0.90},
            {"pos": 1.0, "cyan": 0.60, "magenta": 0.55, "yellow": 0.50, "silver": 0.30},
        ],
    }
    dens = (BIN / "denscore").as_posix()
    proc = subprocess.run(
        [dens],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    out = json.loads(proc.stdout)
    expected = oracle_reel_dens(payload["samples"], payload["temp_c"], payload["rh_pct"])
    for block in ("start", "end", "mid"):
        for c in CHANNELS:
            assert out[block][c] == pytest.approx(expected[block][c], rel=1e-6, abs=1e-6)


def test_matrix_csv_agrees_with_report(fresh_out):
    """CSV rows mirror report gap values and ok flags."""
    case_path = CASES / "festival-continuum-pass.json"
    case = json.loads(case_path.read_text())
    proc = run_case(case_path, fresh_out)
    assert proc.returncode == 0
    report = load_report(fresh_out)
    expected = oracle_case(case)
    assert report["output_digest"] == expected["output_digest"]
    by_key = {}
    for sp in report["splices"]:
        for c in CHANNELS:
            ch_ok = abs(sp["gaps"][c]) <= THR
            by_key[(sp["splice_id"], c)] = (sp["gaps"][c], ch_ok)
    with (fresh_out / "continuum_matrix.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for row in rows:
        gap, ok = by_key[(row["splice_id"], row["channel"])]
        assert float(row["gap"]) == pytest.approx(round6(gap), abs=1e-6)
        assert row["ok"] == str(ok).lower()


def test_resume_second_run_epoch_bump(fresh_out):
    """Second successful run increments epoch and appends history."""
    case_path = CASES / "festival-continuum-pass.json"
    run_case(case_path, fresh_out)
    s1 = json.loads((fresh_out / "continuum_state.json").read_text())
    run_case(case_path, fresh_out)
    s2 = json.loads((fresh_out / "continuum_state.json").read_text())
    assert s2["epoch"] == s1["epoch"] + 1
    hist = (fresh_out / "continuum_history.jsonl").read_text().strip().splitlines()
    assert len(hist) == 2
    ledger = json.loads((fresh_out / "continuum_run_ledger.json").read_text())
    assert len(ledger["runs"]) == 2
