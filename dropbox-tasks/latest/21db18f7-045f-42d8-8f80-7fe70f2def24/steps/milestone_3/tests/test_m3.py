"""Milestone 3 tests: Execution reporting correctness."""

import json
import os
import sqlite3
import subprocess

import pytest
from reference_flaky import (
    expected_execution,
    expected_plan,
    scan_submitted_code_for_verifier_reads,
    write_reference_plan,
)

EXEC_REPORT_PATH = "/app/logs/execution_report.json"
PLAN_PATH = "/app/logs/plan.json"
DB_PATH = "/app/db/history.db"


def run_execution_only():
    if not os.path.exists(PLAN_PATH):
        write_reference_plan()
    result = subprocess.run(
        ["node", "cli.js", "run", "--session", "plan-sess-alpha"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"run failed: {result.stderr}"


def reset_session_execution_results():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "DELETE FROM execution_results "
        "WHERE planned_session_id = 'plan-sess-alpha' AND interrupted = 0"
    )
    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def reference_plan():
    return expected_plan()


@pytest.fixture(scope="module")
def reference_exec(reference_plan):
    return expected_execution(reference_plan)


@pytest.fixture(scope="module")
def exec_report():
    run_execution_only()
    assert os.path.exists(EXEC_REPORT_PATH)
    with open(EXEC_REPORT_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_execution_report_exists(exec_report):
    assert os.path.exists(EXEC_REPORT_PATH)


def test_report_has_required_keys(exec_report):
    for key in ("session_id", "failures", "passed_count", "failed_count", "flaky_count"):
        assert key in exec_report


def test_failure_entries_include_valid_browser(exec_report, reference_exec):
    failures = exec_report.get("failures", [])
    assert len(failures) > 0
    assert {f["spec_file"] for f in failures} == reference_exec["failure_specs"]
    for failure in failures:
        assert "browser" in failure
        assert failure["browser"] in reference_exec["failure_browsers"]
        assert "retry_count" in failure
        assert isinstance(failure["retry_count"], int)
        assert failure["status"] == "failed"


def test_flaky_count_is_correct(exec_report, reference_exec):
    assert isinstance(exec_report["flaky_count"], int)
    assert exec_report["flaky_count"] == reference_exec["flaky_count"]


def test_flaky_count_matches_db(exec_report, reference_exec):
    assert exec_report["flaky_count"] == reference_exec["flaky_count"]


def test_interrupted_rows_excluded_from_counts(exec_report):
    conn = sqlite3.connect(DB_PATH)
    interrupted_count = conn.execute(
        "SELECT COUNT(*) FROM execution_results "
        "WHERE planned_session_id = 'plan-sess-alpha' AND interrupted = 1"
    ).fetchone()[0]
    non_interrupted = conn.execute(
        "SELECT COUNT(*) FROM execution_results "
        "WHERE planned_session_id = 'plan-sess-alpha' AND interrupted = 0"
    ).fetchone()[0]
    conn.close()

    assert interrupted_count > 0
    report_total = exec_report["passed_count"] + exec_report["failed_count"]
    assert report_total == non_interrupted


def test_rerun_produces_consistent_report(exec_report):
    run_execution_only()
    with open(EXEC_REPORT_PATH, encoding="utf-8") as handle:
        second_report = json.load(handle)
    assert second_report["passed_count"] == exec_report["passed_count"]
    assert second_report["failed_count"] == exec_report["failed_count"]


def test_failure_spec_files_match_planned(exec_report, reference_plan):
    planned_specs = {
        spec
        for project in reference_plan["projects"]
        for spec in project["testMatch"]
    }
    for failure in exec_report.get("failures", []):
        assert failure["spec_file"] in planned_specs


def test_counts_match_db_ground_truth(exec_report, reference_exec):
    assert exec_report["passed_count"] == reference_exec["passed_count"]
    assert exec_report["failed_count"] == reference_exec["failed_count"]


def test_z_failure_simulation_reflects_test_runs_history():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "UPDATE test_runs SET status='failed' "
        "WHERE spec_file='tests/e2e/cart.spec.ts' AND browser='webkit' "
        "AND deleted=0 AND parent_session_id IS NULL AND status='passed' "
        "LIMIT 1"
    )
    assert cur.rowcount == 1
    conn.commit()
    conn.close()

    reset_session_execution_results()
    run_execution_only()

    with open(EXEC_REPORT_PATH, encoding="utf-8") as handle:
        report = json.load(handle)

    cart_failures = [
        f for f in report["failures"]
        if f["spec_file"] == "tests/e2e/cart.spec.ts" and f["browser"] == "webkit"
    ]
    assert len(cart_failures) == 1

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE test_runs SET status='passed' "
        "WHERE spec_file='tests/e2e/cart.spec.ts' AND browser='webkit' "
        "AND deleted=0 AND parent_session_id IS NULL AND session_id='sess-005'"
    )
    conn.commit()
    conn.close()


def test_z_interrupted_rows_preserved_on_rerun():
    run_execution_only()
    conn = sqlite3.connect(DB_PATH)
    interrupted = conn.execute(
        "SELECT COUNT(*) FROM execution_results "
        "WHERE planned_session_id='plan-sess-alpha' AND interrupted=1"
    ).fetchone()[0]
    conn.close()
    assert interrupted >= 1


def test_z_executor_ignores_deleted_test_runs():
    conn = sqlite3.connect(DB_PATH)
    for i in range(3):
        conn.execute(
            "INSERT INTO test_runs "
            "(spec_file, browser, status, duration_ms, retry_attempt, "
            "session_id, parent_session_id, deleted, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tests/e2e/search.spec.ts",
                "webkit",
                "failed",
                1000,
                0,
                f"deleted-inject-{i}",
                None,
                1,
                99999 + i,
            ),
        )
    conn.commit()
    conn.close()

    reset_session_execution_results()
    run_execution_only()

    with open(EXEC_REPORT_PATH, encoding="utf-8") as handle:
        report = json.load(handle)

    webkit_search_failures = [
        f for f in report["failures"]
        if f["spec_file"] == "tests/e2e/search.spec.ts" and f["browser"] == "webkit"
    ]
    assert len(webkit_search_failures) == 0

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM test_runs WHERE session_id LIKE 'deleted-inject-%'")
    conn.commit()
    conn.close()


def test_z_executor_ignores_rerun_sessions():
    conn = sqlite3.connect(DB_PATH)
    for i in range(3):
        conn.execute(
            "INSERT INTO test_runs "
            "(spec_file, browser, status, duration_ms, retry_attempt, "
            "session_id, parent_session_id, deleted, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tests/e2e/search.spec.ts",
                "webkit",
                "failed",
                1000,
                1,
                f"rerun-inject-{i}",
                "sess-001",
                0,
                199999 + i,
            ),
        )
    conn.commit()
    conn.close()

    reset_session_execution_results()
    run_execution_only()

    with open(EXEC_REPORT_PATH, encoding="utf-8") as handle:
        report = json.load(handle)

    webkit_search_failures = [
        f for f in report["failures"]
        if f["spec_file"] == "tests/e2e/search.spec.ts" and f["browser"] == "webkit"
    ]
    assert len(webkit_search_failures) == 0

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM test_runs WHERE session_id LIKE 'rerun-inject-%'")
    conn.commit()
    conn.close()


def test_z_submitted_code_does_not_read_verifier_paths():
    hits = scan_submitted_code_for_verifier_reads()
    assert hits == [], (
        "Submitted application code must not read verifier paths: " + "; ".join(hits)
    )
