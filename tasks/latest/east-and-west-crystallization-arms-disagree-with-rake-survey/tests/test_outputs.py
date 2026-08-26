"""Verifier for salt pond crystallization simulation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "front_report.json"
MEMO = APP / "output" / ".sector_memo.json"
FIX = Path("/tests/fixtures")
REBUILD = Path("/tests/harness/rebuild.sh")
INVOKE = Path("/tests/harness/invoke.sh")

REFERENCE = json.loads(
    """
{
    "pond_alpha": {
        "schema_version": "1",
        "pond_id": "pond_alpha",
        "mast_epoch": 3,
        "arms": [
            {
                "arm_key": "L1",
                "front_m": 4.0,
                "advance_cmd": 4.0,
                "survey_m": 5.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L2",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 4.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L3",
                "front_m": 5.0,
                "advance_cmd": 5.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L4",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            }
        ],
        "daily_fronts": [
            {
                "day": 1,
                "vertices": [
                    {
                        "arm_key": "L1",
                        "front_m": 5.0
                    },
                    {
                        "arm_key": "L2",
                        "front_m": 4.0
                    },
                    {
                        "arm_key": "L3",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L4",
                        "front_m": 0.0
                    }
                ]
            }
        ],
        "calm_latch_events": 0,
        "survey_mismatch": 3,
        "front_sum": 90,
        "digest_hex": "63411af8d6b7c3a73ffbf67a508de20250839f7202e5b384312632076626ab3f"
    },
    "pond_beta": {
        "schema_version": "1",
        "pond_id": "pond_beta",
        "mast_epoch": 4,
        "arms": [
            {
                "arm_key": "L1",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 6.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L2",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L3",
                "front_m": 6.0,
                "advance_cmd": 6.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L4",
                "front_m": 0.75,
                "advance_cmd": 0.75,
                "survey_m": 0.0,
                "telemetry_ok": true
            }
        ],
        "daily_fronts": [
            {
                "day": 1,
                "vertices": [
                    {
                        "arm_key": "L1",
                        "front_m": 6.0
                    },
                    {
                        "arm_key": "L2",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L3",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L4",
                        "front_m": 0.0
                    }
                ]
            }
        ],
        "calm_latch_events": 1,
        "survey_mismatch": 3,
        "front_sum": 68,
        "digest_hex": "1a179a97f09a880d9589b70da667cd075dcf52b6a63fcd8d615a6b6825eb9144"
    },
    "pond_gamma": {
        "schema_version": "1",
        "pond_id": "pond_gamma",
        "mast_epoch": 3,
        "arms": [
            {
                "arm_key": "L1",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 7.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L2",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L3",
                "front_m": 10.0,
                "advance_cmd": 3.0,
                "survey_m": 3.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L4",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            }
        ],
        "daily_fronts": [
            {
                "day": 2,
                "vertices": [
                    {
                        "arm_key": "L1",
                        "front_m": 7.0
                    },
                    {
                        "arm_key": "L2",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L3",
                        "front_m": 3.0
                    },
                    {
                        "arm_key": "L4",
                        "front_m": 0.0
                    }
                ]
            }
        ],
        "calm_latch_events": 0,
        "survey_mismatch": 2,
        "front_sum": 100,
        "digest_hex": "d1abf05489e9e068c2eee69308a65c4c09b1510fcb6d0d121974ad3261670ad5"
    },
    "pond_delta": {
        "schema_version": "1",
        "pond_id": "pond_delta",
        "mast_epoch": 3,
        "arms": [
            {
                "arm_key": "L1",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L2",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L3",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L4",
                "front_m": 6.0,
                "advance_cmd": 6.0,
                "survey_m": 6.0,
                "telemetry_ok": true
            }
        ],
        "daily_fronts": [
            {
                "day": 3,
                "vertices": [
                    {
                        "arm_key": "L1",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L2",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L3",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L4",
                        "front_m": 6.0
                    }
                ]
            }
        ],
        "calm_latch_events": 0,
        "survey_mismatch": 0,
        "front_sum": 60,
        "digest_hex": "73282c58bbc7aa471e2284b7c24031d3f487263426ea15032f2837612d2c2488"
    },
    "pond_epsilon": {
        "schema_version": "1",
        "pond_id": "pond_epsilon",
        "mast_epoch": 3,
        "arms": [
            {
                "arm_key": "L1",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L2",
                "front_m": 5.0,
                "advance_cmd": 5.0,
                "survey_m": 5.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L3",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            },
            {
                "arm_key": "L4",
                "front_m": 0.0,
                "advance_cmd": 0.0,
                "survey_m": 0.0,
                "telemetry_ok": true
            }
        ],
        "daily_fronts": [
            {
                "day": 4,
                "vertices": [
                    {
                        "arm_key": "L1",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L2",
                        "front_m": 5.0
                    },
                    {
                        "arm_key": "L3",
                        "front_m": 0.0
                    },
                    {
                        "arm_key": "L4",
                        "front_m": 0.0
                    }
                ]
            }
        ],
        "calm_latch_events": 0,
        "survey_mismatch": 0,
        "front_sum": 50,
        "digest_hex": "c452390260be5ba1e0d3a850508476aa44fb89718136a9102df5a61942023a7e"
    }
}
"""
)


def _expected(name: str) -> dict:
    return REFERENCE[name]


def _stage_pond(name: str) -> None:
    src = FIX / name
    dst = APP / "data" / "active"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _run_driver() -> dict:
    subprocess.run(["bash", str(INVOKE)], check=True, cwd=str(APP))
    return json.loads(OUT.read_text())


@pytest.fixture(scope="module", autouse=True)
def _build_once():
    subprocess.run(["bash", str(REBUILD)], check=True, cwd=str(APP))
    yield


class TestPondAlpha:
    def test_mast_epoch_pond_alpha(self):
        """mast_epoch must match the active pond plan calibration generation."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        rep = _run_driver()
        exp = _expected("pond_alpha")
        assert rep["mast_epoch"] == exp["mast_epoch"] == 3

    def test_arm_lane_order_pond_alpha(self):
        """arms must follow arm_lane packing order with L{arm_id} keys."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        rep = _run_driver()
        keys = [a["arm_key"] for a in rep["arms"]]
        # Packing order is L1..L4; require the first two slots so partial
        # remaps that still leave L1 leading are distinguishable from label sort.
        assert keys[:2] == ["L1", "L2"]
        assert set(keys) == {"L1", "L2", "L3", "L4"}

    def test_survey_mismatch_pond_alpha(self):
        """Survey mismatch count must match deterministic simulation for pond_alpha."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        rep = _run_driver()
        exp = _expected("pond_alpha")
        assert rep["survey_mismatch"] == exp["survey_mismatch"]
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L1"]["front_m"] == exp["arms"][0]["front_m"]
        assert by_key["L1"]["survey_m"] == exp["arms"][0]["survey_m"]


class TestPondBeta:
    def test_resume_calm_latch_pond_beta(self):
        """Mid-tape resume must preserve latch memory across the continuation."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_beta")
        assert (APP / "data" / "active" / "resume_state.json").is_file()
        rep = _run_driver()
        exp = _expected("pond_beta")
        assert rep["calm_latch_events"] == exp["calm_latch_events"] == 1
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L3"]["front_m"] == 6.0
        assert by_key["L4"]["front_m"] == 0.75

    def test_mast_epoch_pond_beta(self):
        """mast_epoch must clear the service floor on pond_beta's calibration generation."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_beta")
        rep = _run_driver()
        assert rep["mast_epoch"] == 4


class TestPondGamma:
    def test_arm_front_pond_gamma(self):
        """Wind-driven advance must land on the correct pond arm for the active wind tape."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_gamma")
        rep = _run_driver()
        exp = _expected("pond_gamma")
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L3"]["front_m"] == exp["arms"][2]["front_m"]
        assert rep["front_sum"] == exp["front_sum"]

    def test_daily_vertices_pond_gamma(self):
        """Per-day survey vertices must carry the expected rake readings for pond_gamma."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_gamma")
        rep = _run_driver()
        by_day = {d["day"]: d for d in rep["daily_fronts"]}
        assert 2 in by_day
        verts_list = by_day[2]["vertices"]
        assert verts_list, "day-2 vertices missing"
        assert verts_list[0]["arm_key"] == "L1"
        verts = {v["arm_key"]: v["front_m"] for v in verts_list}
        assert verts.get("L1") == 7.0
        assert verts.get("L3") == 3.0


class TestPondDelta:
    def test_arm_front_pond_delta(self):
        """Sector routing must advance the expected arm front for the active wind tape."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_delta")
        rep = _run_driver()
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L4"]["front_m"] == 6.0
        assert by_key["L2"]["front_m"] == 0.0

    def test_pack_swap_memo_alpha_then_delta(self):
        """Routing memo from a prior pack must not poison a later pack with a different table."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        _run_driver()
        _stage_pond("pond_delta")
        rep = _run_driver()
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L4"]["front_m"] == 6.0
        assert by_key["L2"]["front_m"] == 0.0
        assert by_key["L3"]["front_m"] == 0.0
        assert rep["pond_id"] == "pond_delta"


class TestPondEpsilon:
    def test_survey_mismatch_pond_epsilon(self):
        """Survey mismatch must reflect plan survey-layer agreement with wind-integrated fronts."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_epsilon")
        rep = _run_driver()
        exp = _expected("pond_epsilon")
        assert rep["survey_mismatch"] == exp["survey_mismatch"]
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L2"]["survey_m"] == 5.0
        assert by_key["L2"]["front_m"] == 5.0


class TestIntegrity:
    def test_digest_matches_fields(self):
        """digest_hex must match the folded integrity payload from the active simulation."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        rep = _run_driver()
        exp = _expected("pond_alpha")
        assert rep["digest_hex"] == exp["digest_hex"]

    def test_active_bundle_simulation(self):
        """Bundled active scenario must simulate correctly without swapping scenarios."""
        if MEMO.exists():
            MEMO.unlink()
        _stage_pond("pond_alpha")
        rep = _run_driver()
        exp = _expected("pond_alpha")
        assert rep["pond_id"] == exp["pond_id"]
        assert rep["schema_version"] == "1"
        assert rep["mast_epoch"] == exp["mast_epoch"]
        by_key = {a["arm_key"]: a for a in rep["arms"]}
        assert by_key["L1"]["front_m"] == exp["arms"][0]["front_m"]
        assert by_key["L3"]["front_m"] == exp["arms"][2]["front_m"]
        assert rep["digest_hex"] == exp["digest_hex"]
