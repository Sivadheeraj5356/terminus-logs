import json
import os
import subprocess
from pathlib import Path

import pytest

REPORT_PATH = Path("/app/ingest_recovery_report.json")
WORKLOADS_PATH = Path("/app/environment/data/workloads.json")
ENV_DIR = Path("/app/environment")

SIM_SECONDS_PER_TICK = 0.01
MAX_COMMITS_PER_1000 = 2.0
MAX_ASSIGNMENT_SPREAD = 1
COMMIT_BAND = 0.15
THROUGHPUT_EFFICIENCY = 0.80
TICK_SLACK_FACTOR = 2

EXPECTED_PLACEMENT_SIGNATURE = {
    "burst_orders": 24,
    "steady_telemetry": 21,
    "skewed_keys": 46,
    "hotfix_replay": 21,
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(text: str) -> str:
    proc = subprocess.run(
        ["python3", "/app/environment/tools/check_digest.py", text],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _expected_records(scenario: dict) -> int:
    return scenario["partitions"] * scenario["records_per_partition"]


def _loads_are_equitable(loads: list[int], partitions: int) -> bool:
    if sum(loads) != partitions:
        return False
    if not loads:
        return partitions == 0
    return max(loads) - min(loads) <= MAX_ASSIGNMENT_SPREAD


def _placement_signature(loads: list[int]) -> int:
    return sum((i + 1) * load for i, load in enumerate(loads))


def _target_commits_per_1000(interval: int) -> float:
    return round(1000.0 / interval, 2)


def _throughput_floor(scenario: dict) -> float:
    return (
        THROUGHPUT_EFFICIENCY
        * scenario["partitions"]
        * scenario["max_poll_records"]
        / SIM_SECONDS_PER_TICK
    )


def _tick_ceiling(records: int, scenario: dict) -> int:
    pace = scenario["partitions"] * scenario["max_poll_records"]
    assert pace > 0
    ideal = (records + pace - 1) // pace
    return ideal * TICK_SLACK_FACTOR


def _recovery_digest(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda row: row["scenario_id"])
    payload = "".join(
        f"{row['scenario_id']}:{row['records_processed']}:{row['final_residual_records']}:"
        f"{row['peak_tick_residual']}:{row['commits_per_1000_records']:.2f}:"
        f"{row['assignment_spread']}:{row['idle_member_count']}:{row['placement_signature']}"
        for row in ordered
    )
    return _digest(payload)


def _rerun_stream_bench() -> None:
    """Rebuild the report from source after deleting any prior output."""
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    env = {
        **os.environ,
        "GOCACHE": "/tmp/go-build",
        "GOMODCACHE": "/tmp/go-mod",
    }
    proc = subprocess.run(
        [
            "go",
            "run",
            "/app/environment/cmd/stream-bench",
            "--workloads",
            "/app/environment/data/workloads.json",
            "--cluster",
            "/app/environment/configs/cluster.json",
            "--report",
            "/app/ingest_recovery_report.json",
        ],
        cwd=ENV_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


@pytest.fixture(scope="module", autouse=True)
def regenerated_report():
    """Every test reads a report rebuilt from current source, not a stale artifact."""
    _rerun_stream_bench()


def test_check_digest_helper_contract():
    """check_digest.py must stay a text-in/digest-out helper for verifier use."""
    for probe in ("probe", "x"):
        proc = subprocess.run(
            ["python3", "/app/environment/tools/check_digest.py", probe],
            capture_output=True,
            text=True,
            check=True,
        )
        digest = proc.stdout.strip()
        assert len(digest) == 64
        assert digest.islower()
        int(digest, 16)


def test_report_rebuilt_from_source():
    """Report must be rebuilt from Go source, not a static hand-written file."""
    first = REPORT_PATH.read_bytes()
    _rerun_stream_bench()
    second = REPORT_PATH.read_bytes()
    assert REPORT_PATH.is_file()
    assert first == second


def test_report_schema_and_scenario_coverage():
    """Report must include every workload scenario with required observation fields."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    assert "scenarios" in report
    assert "recovery_digest" in report
    expected_ids = {row["scenario_id"] for row in workloads["scenarios"]}
    got_ids = {row["scenario_id"] for row in report["scenarios"]}
    assert got_ids == expected_ids
    required = {
        "scenario_id",
        "records_processed",
        "ticks_elapsed",
        "final_residual_records",
        "peak_tick_residual",
        "throughput_records_per_sec",
        "commits_per_1000_records",
        "assignment_spread",
        "member_loads",
        "idle_member_count",
        "placement_signature",
    }
    for row in report["scenarios"]:
        assert required <= set(row)


def test_all_scenarios_fully_drain_fixtures():
    """Each scenario must process every seeded record in its broker fixture."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        expected = _expected_records(by_id[row["scenario_id"]])
        assert row["records_processed"] == expected


def test_final_residual_cleared():
    """Residual backlog at scenario end must be zero for every scenario."""
    report = _load_json(REPORT_PATH)
    for row in report["scenarios"]:
        assert row["final_residual_records"] == 0


def test_no_idle_member_slots():
    """Every member slot must own at least one lane when the scenario drains."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        assert row["idle_member_count"] == 0
        if sc["partitions"] >= sc["members"]:
            assert all(load > 0 for load in row["member_loads"])


def test_placement_signature_and_loads():
    """Loads and placement_signature must satisfy the contract formulas."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        loads = row["member_loads"]
        assert _loads_are_equitable(loads, sc["partitions"])
        assert row["placement_signature"] == _placement_signature(loads)
        assert row["placement_signature"] == EXPECTED_PLACEMENT_SIGNATURE[row["scenario_id"]]
        assert row["assignment_spread"] == max(loads) - min(loads)
        assert row["assignment_spread"] <= MAX_ASSIGNMENT_SPREAD


def test_commit_rate_tracks_interval_band():
    """Commit rate must stay near 1000/commit_interval_records, not only under a ceiling."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        target = _target_commits_per_1000(sc["commit_interval_records"])
        rate = row["commits_per_1000_records"]
        assert rate <= MAX_COMMITS_PER_1000
        assert abs(rate - target) <= COMMIT_BAND, (
            f"{row['scenario_id']}: commits_per_1000={rate} target={target} band={COMMIT_BAND}"
        )


def test_throughput_meets_scenario_floor():
    """Throughput must meet the per-scenario efficiency floor derived from workload knobs."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        seconds = row["ticks_elapsed"] * SIM_SECONDS_PER_TICK
        derived = round(row["records_processed"] / seconds, 2)
        assert row["throughput_records_per_sec"] == derived
        floor = _throughput_floor(sc)
        assert row["throughput_records_per_sec"] >= floor, (
            f"{row['scenario_id']}: throughput={row['throughput_records_per_sec']} floor={floor}"
        )


def test_ticks_within_capacity_bound():
    """Ticks must beat the shared budget and stay within 2x ideal capacity for full pulls."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    budget = workloads["tick_budget"]
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        assert row["ticks_elapsed"] < budget
        ceiling = _tick_ceiling(row["records_processed"], sc)
        assert row["ticks_elapsed"] <= ceiling, (
            f"{row['scenario_id']}: ticks={row['ticks_elapsed']} ceiling={ceiling}"
        )


def test_recovery_digest_matches_observations():
    """recovery_digest must hash the contract-defined scenario observation string."""
    report = _load_json(REPORT_PATH)
    assert report["recovery_digest"] == _recovery_digest(report["scenarios"])
    assert len(report["recovery_digest"]) == 64


def test_drain_commit_throughput_joint():
    """Healthy rows must jointly satisfy drain, placement, commit band, and throughput."""
    report = _load_json(REPORT_PATH)
    workloads = _load_json(WORKLOADS_PATH)
    by_id = {row["scenario_id"]: row for row in workloads["scenarios"]}
    for row in report["scenarios"]:
        sc = by_id[row["scenario_id"]]
        assert row["records_processed"] == _expected_records(sc)
        assert row["final_residual_records"] == 0
        assert row["idle_member_count"] == 0
        rate = row["commits_per_1000_records"]
        target = _target_commits_per_1000(sc["commit_interval_records"])
        assert abs(rate - target) <= COMMIT_BAND
        assert row["throughput_records_per_sec"] >= _throughput_floor(sc)
        loads = row["member_loads"]
        assert _loads_are_equitable(loads, sc["partitions"])
        assert row["placement_signature"] == EXPECTED_PLACEMENT_SIGNATURE[row["scenario_id"]]
