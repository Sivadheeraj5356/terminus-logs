"""Verifier tests for the tournament Elo rating pipeline JSON report."""
import hashlib
import json
import math
import os
import subprocess

import pytest


def load_report():
    """Load the JSON report produced by the Elo rating pipeline."""
    with open("/tmp/test_report.json") as f:
        return json.load(f)


def run_pipeline(trace_path=None, output_path=None):
    """Rebuild and run the pipeline to produce fresh output."""
    subprocess.run(
        ["bash", "/app/environment/scripts/rebuild.sh"],
        capture_output=True,
        timeout=120,
    )
    src = "/app/environment/target/release/elo_verify"
    dst = "/app/environment/elo_verify"
    if os.path.exists(src):
        subprocess.run(["cp", src, dst], capture_output=True, timeout=10)

    binary = dst if os.path.exists(dst) else src
    trace = trace_path or "/app/environment/traces/match_trace.csv"
    out = output_path or "/tmp/test_report.json"
    subprocess.run(
        [binary, trace, out],
        capture_output=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Independent Python reference implementation of the Elo pipeline
# ---------------------------------------------------------------------------

def _parse_matches(path):
    """Parse the CSV trace into a list of match dicts."""
    matches = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("match_id"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                matches.append({
                    "match_id": parts[0],
                    "player_a": parts[1],
                    "player_b": parts[2],
                    "score_a": float(parts[3]),
                    "score_b": float(parts[4]),
                    "tournament_tier": parts[5],
                })
    return matches


def _compute_expected(matches):
    """
    Compute the full Elo pipeline result independently.

    Correct behaviour:
      - Scores pass through unchanged for every tier.
      - Elo divisor is 400.
      - K = 32 on every match.
      - rating_stability = max(0, 100 - avg_rating_change).
      - Status thresholds: VALID > 70, REVIEW > 40, else INVALID.
      - false_volatility uses baseline = players * matches * 10.
    """
    ratings = {}
    all_changes = []

    for m in matches:
        pa, pb = m["player_a"], m["player_b"]
        ratings.setdefault(pa, 1500.0)
        ratings.setdefault(pb, 1500.0)

        ra, rb = ratings[pa], ratings[pb]
        expected_a = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
        expected_b = 1.0 - expected_a

        actual_a = 1.0 if m["score_a"] > m["score_b"] else 0.0
        actual_b = 1.0 - actual_a

        k = 32.0
        change_a = k * (actual_a - expected_a)
        change_b = k * (actual_b - expected_b)

        ratings[pa] += change_a
        ratings[pb] += change_b
        all_changes.extend([abs(change_a), abs(change_b)])

    total_matches = len(matches)
    players_rated = len(ratings)
    updates = len(all_changes)
    avg_change = sum(all_changes) / updates if updates else 0.0

    stability = max(0.0, 100.0 - avg_change)
    quality = stability

    baseline = players_rated * total_matches * 10.0
    variance_factor = avg_change * total_matches
    false_vol = (
        math.ceil((variance_factor - baseline) / baseline)
        if variance_factor > baseline
        else 0
    )

    if quality > 70.0:
        status = "VALID"
    elif quality > 40.0:
        status = "REVIEW"
    else:
        status = "INVALID"

    return {
        "total_matches": total_matches,
        "players_rated": players_rated,
        "avg_rating_change": avg_change,
        "skipped_updates": 0,
        "optimal_k": 32.0,
        "rating_stability": stability,
        "false_volatility": false_vol,
        "ranking_quality": quality,
        "tournament_status": status,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TRACE_PATH = "/app/environment/traces/match_trace.csv"


@pytest.fixture(scope="session", autouse=True)
def pipeline_output():
    """Build and run pipeline once for all tests."""
    run_pipeline()


@pytest.fixture(scope="session")
def expected():
    """Pre-compute expected values from the independent reference."""
    matches = _parse_matches(TRACE_PATH)
    return _compute_expected(matches)


# ---------------------------------------------------------------------------
# Tests — Elo formula correctness (divisor = 400)
# ---------------------------------------------------------------------------

class TestEloComputation:
    """Verify the pipeline computes Elo ratings with divisor 400."""

    def test_total_matches(self, expected):
        """Verify total_matches count matches reference."""
        r = load_report()
        assert r["analysis"]["elo"]["total_matches"] == expected["total_matches"]

    def test_players_rated(self, expected):
        """Verify players_rated count matches reference."""
        r = load_report()
        assert r["analysis"]["elo"]["players_rated"] == expected["players_rated"]

    def test_skipped_updates_zero(self, expected):
        """Verify skipped_updates is 0 for valid run."""
        r = load_report()
        assert r["analysis"]["elo"]["skipped_updates"] == 0

    def test_avg_rating_change(self, expected):
        """Verify avg_rating_change within tolerance of reference."""
        r = load_report()
        avg = r["analysis"]["elo"]["avg_rating_change"]
        assert abs(avg - expected["avg_rating_change"]) < 0.5, (
            f"avg_rating_change {avg} deviates from expected {expected['avg_rating_change']}"
        )

    def test_optimal_k(self, expected):
        """Verify optimal_k is constant 32."""
        r = load_report()
        assert r["analysis"]["optimal_k"] == 32.0

    def test_false_volatility_zero(self, expected):
        """Verify false_volatility is 0 for stable system."""
        r = load_report()
        assert r["analysis"]["false_volatility"] == 0


# ---------------------------------------------------------------------------
# Tests — score passthrough (no tier-based transformation)
# ---------------------------------------------------------------------------

class TestScorePassthrough:
    """Verify scores pass through unchanged regardless of tier."""

    def test_quality_consistent_with_correct_scores(self, expected):
        """If scores are swapped/transformed for any tier, quality will differ."""
        r = load_report()
        q = r["ranking_quality"]
        assert abs(q - expected["ranking_quality"]) < 2.0, (
            f"ranking_quality {q} deviates from expected {expected['ranking_quality']}"
        )

    def test_stability_consistent(self, expected):
        """Verify rating_stability matches reference within tolerance."""
        r = load_report()
        s = r["analysis"]["rating_stability"]
        assert abs(s - expected["rating_stability"]) < 2.0, (
            f"rating_stability {s} deviates from expected {expected['rating_stability']}"
        )


# ---------------------------------------------------------------------------
# Tests — stability formula (100 - avg, not 100 - avg * 2)
# ---------------------------------------------------------------------------

class TestStabilityFormula:
    """Verify rating_stability = max(0, 100 - avg_rating_change)."""

    def test_stability_matches_formula(self, expected):
        """Verify stability = max(0, 100 - avg_rating_change)."""
        r = load_report()
        avg = r["analysis"]["elo"]["avg_rating_change"]
        stab = r["analysis"]["rating_stability"]
        correct_stab = max(0.0, 100.0 - avg)
        assert abs(stab - correct_stab) < 0.5, (
            f"stability {stab} != 100 - avg({avg}) = {correct_stab}"
        )

    def test_quality_equals_stability(self, expected):
        """Verify ranking_quality equals rating_stability."""
        r = load_report()
        assert abs(r["ranking_quality"] - r["analysis"]["rating_stability"]) < 0.01


# ---------------------------------------------------------------------------
# Tests — status thresholds (70 / 40)
# ---------------------------------------------------------------------------

class TestStatusThresholds:
    """Verify tournament status uses thresholds 70 and 40."""

    def test_valid_status(self, expected):
        """Verify tournament_status is VALID for this trace."""
        r = load_report()
        assert r["tournament_status"] == "VALID"

    def test_status_matches_thresholds(self, expected):
        """Verify status matches thresholds: >70 VALID, >40 REVIEW, else INVALID."""
        r = load_report()
        q = r["ranking_quality"]
        status = r["tournament_status"]
        if q > 70.0:
            assert status == "VALID", f"quality {q} > 70 should be VALID, got {status}"
        elif q > 40.0:
            assert status == "REVIEW", f"quality {q} > 40 should be REVIEW, got {status}"
        else:
            assert status == "INVALID", f"quality {q} <= 40 should be INVALID, got {status}"


# ---------------------------------------------------------------------------
# Tests — file integrity (protect traces and verifier tool)
# ---------------------------------------------------------------------------

class TestFileIntegrity:
    """Verify protected files have not been modified."""

    def test_trace_hash(self):
        """Verify trace file has not been modified."""
        with open("/app/environment/traces/match_trace.csv", "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        assert h == "16a0774f092a00fd4a24ca613af79367ad575347f0acd16b6e283965f1309516"

    def test_verifier_source_hash(self):
        """Verify elo_verify source has not been modified."""
        with open("/app/environment/tools/elo_verify/main.rs", "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        assert h == "2b252f8734163040a2d21bbd6763a9492d69ff7140187b0e01862c06020e8182"


# ---------------------------------------------------------------------------
# Tests — private trace (general Elo behavior on unseen data)
# ---------------------------------------------------------------------------

PRIVATE_TRACE = """\
match_id,player_a,player_b,score_a,score_b,tournament_tier
T001,Alpha,Bravo,1.0,0.0,STANDARD
T002,Charlie,Delta,0.0,1.0,STANDARD
T003,Alpha,Charlie,1.0,0.0,GRAND
T004,Bravo,Delta,0.5,0.5,STANDARD
T005,Alpha,Delta,1.0,0.0,STANDARD
T006,Bravo,Charlie,0.0,1.0,GRAND
"""


class TestPrivateTrace:
    """Run pipeline on a private trace and verify against Python reference."""

    @pytest.fixture(autouse=True)
    def _run_private(self, tmp_path):
        trace_file = tmp_path / "private.csv"
        trace_file.write_text(PRIVATE_TRACE)
        self.output_file = str(tmp_path / "private_report.json")
        run_pipeline(str(trace_file), self.output_file)
        with open(self.output_file) as f:
            self.report = json.load(f)
        matches = []
        for line in PRIVATE_TRACE.strip().split("\n")[1:]:
            parts = [p.strip() for p in line.split(",")]
            matches.append({
                "match_id": parts[0], "player_a": parts[1], "player_b": parts[2],
                "score_a": float(parts[3]), "score_b": float(parts[4]),
                "tournament_tier": parts[5],
            })
        self.expected = _compute_expected(matches)

    def test_private_total_matches(self):
        """Verify total_matches on private trace."""
        assert self.report["analysis"]["elo"]["total_matches"] == self.expected["total_matches"]

    def test_private_players_rated(self):
        """Verify players_rated on private trace."""
        assert self.report["analysis"]["elo"]["players_rated"] == self.expected["players_rated"]

    def test_private_avg_rating_change(self):
        """Verify avg_rating_change on private trace within tolerance."""
        avg = self.report["analysis"]["elo"]["avg_rating_change"]
        assert abs(avg - self.expected["avg_rating_change"]) < 0.5

    def test_private_status(self):
        """Verify tournament_status on private trace."""
        assert self.report["tournament_status"] == self.expected["tournament_status"]

    def test_private_stability(self):
        """Verify rating_stability on private trace within tolerance."""
        stab = self.report["analysis"]["rating_stability"]
        assert abs(stab - self.expected["rating_stability"]) < 0.5


# ---------------------------------------------------------------------------
# Tests — output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def test_is_dict(self):
        """Verify report is a dict."""
        assert isinstance(load_report(), dict)

    def test_required_top_fields(self):
        """Verify required top-level fields present."""
        r = load_report()
        for f in ["analysis", "ranking_quality", "tournament_status"]:
            assert f in r

    def test_nested_elo_fields(self):
        """Verify nested elo fields present."""
        r = load_report()
        elo = r["analysis"]["elo"]
        for f in ["total_matches", "players_rated", "avg_rating_change", "skipped_updates"]:
            assert f in elo

    def test_no_null_values(self):
        """Verify no null values in report."""
        r = load_report()
        for k, v in r.items():
            assert v is not None, f"Null value for key {k}"

    def test_deterministic(self):
        """Verify pipeline output is deterministic."""
        with open("/tmp/test_report.json") as f:
            c1 = f.read()
        run_pipeline()
        with open("/tmp/test_report.json") as f:
            c2 = f.read()
        assert json.loads(c1) == json.loads(c2), "Pipeline output is non-deterministic"
