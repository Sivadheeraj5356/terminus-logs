from __future__ import annotations

import csv
import math
import shutil
from pathlib import Path

import pytest

from reference import compile_solver, expected, run_solver


PUBLIC = Path("/app/environment/data")
HIDDEN_ROOT = Path("/tests/hidden_data")
FIXTURES = [
    PUBLIC,
    HIDDEN_ROOT / "hidden_clean_early",
    HIDDEN_ROOT / "hidden_april_gap_heavy",
    HIDDEN_ROOT / "hidden_july_gap_transition",
    HIDDEN_ROOT / "hidden_august_gap_heavy",
    HIDDEN_ROOT / "hidden_january_missing_waterheat",
]
TOL = 1e-9


@pytest.fixture(scope="session", autouse=True)
def _compile():
    compile_solver()


def assert_float(actual, exp, label):
    if exp is None:
        assert actual is None, label
        return
    assert isinstance(actual, (int, float)), label
    assert math.isfinite(actual), label
    assert abs(float(actual) - float(exp)) <= TOL, label


def assert_output(actual, exp):
    for key in ("n_events", "n_predictions", "n_labels", "n_missing_events"):
        assert actual.get(key) == exp[key], key
    assert len(actual.get("predictions", [])) == len(exp["predictions"])
    for index, (got, want) in enumerate(zip(actual["predictions"], exp["predictions"])):
        assert got["request_id"] == want["request_id"], f"request id {index}"
        assert got["event_id"] == want["event_id"], f"event id {index}"
        assert_float(got["probability"], want["probability"], f"probability {index}")
    assert actual.get("resets") == exp["resets"]
    assert len(actual.get("windows", [])) == len(exp["windows"])
    for got, want in zip(actual["windows"], exp["windows"]):
        assert got["window_id"] == want["window_id"]
        assert got["n_scored"] == want["n_scored"]
        assert_float(got["brier"], want["brier"], f"brier {want['window_id']}")
        assert_float(got["log_loss"], want["log_loss"], f"log_loss {want['window_id']}")
    final = actual.get("final_state", {})
    assert final.get("gap_events") == exp["final_state"]["gap_events"]
    assert final.get("labels_applied") == exp["final_state"]["labels_applied"]
    got_parts = {row["daypart_id"]: row for row in final.get("dayparts", [])}
    for want in exp["final_state"]["dayparts"]:
        got = got_parts[want["daypart_id"]]
        for key in ("pos", "weight", "ph", "resid_mean", "seen", "cooldown"):
            assert_float(got[key], want[key], f"{want['daypart_id']} {key}")


@pytest.mark.parametrize("data_dir", FIXTURES, ids=[path.name for path in FIXTURES])
def test_stream_replay_matches_independent_oracle(data_dir):
    """Verify every stream matches the independent oracle."""
    exp = expected(data_dir)
    actual = run_solver(data_dir)
    assert_output(actual, exp)


def test_duplicate_requests_share_same_pre_label_probability():
    """Verify duplicate requests share pre-label probabilities."""
    output = run_solver(PUBLIC)
    by_event = {}
    for prediction in output["predictions"]:
        by_event.setdefault(prediction["event_id"], []).append(prediction)
    duplicate_groups = [items for items in by_event.values() if len(items) > 1]
    assert duplicate_groups, "fixture should contain duplicate requests"
    for group in duplicate_groups:
        probs = {round(float(item["probability"]), 12) for item in group}
        assert len(probs) == 1


def test_readings_column_order_is_header_driven(tmp_path):
    """Verify readings parsing is header driven."""
    work = tmp_path / "permuted"
    shutil.copytree(PUBLIC, work)
    readings = work / "readings.csv"
    rows = list(csv.DictReader(readings.open(newline="", encoding="utf-8")))
    fieldnames = [
        "missing_flag",
        "sub_metering_2_wh",
        "event_id",
        "local_time",
        "global_intensity_a",
        "daypart_id",
        "global_active_power_kw",
        "sub_metering_1_wh",
        "voltage_v",
        "global_reactive_power_kvar",
        "local_date",
    ]
    with readings.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    assert_output(run_solver(work), expected(work))
