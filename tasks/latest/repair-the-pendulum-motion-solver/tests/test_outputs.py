"""Verifier tests for the pendulum motion recovery task."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

APP = Path("/app")
DB_PATH = APP / "pendulum_captures.duckdb"
PRISTINE_DB = Path("/opt/seed/pendulum_captures.duckdb")
DRIVER = APP / "recover_motion.py"
# Bundled report CLI shipped from environment/pendulum_recovery/report.py.
REPORT_SCRIPT = Path("/app/environment/pendulum_recovery/report.py")
DOT_PATH = APP / "recovery_graph.dot"
SVG_PATH = APP / "recovery_graph.svg"

NUM_JOBS = 4
JOB_IDS = [1, 2, 3, 4]
GROUND_TRUTH = {
    1: (0.90, 0.35),
    2: (1.30, 0.55),
    3: (1.75, 0.80),
    4: (2.20, 1.10),
}
EXPECTED_REJECTED = {1: 5, 2: 7, 3: 6, 4: 8}
FREQ_REL_TOL = 0.05
DECAY_REL_TOL = 0.10
OUTPUT_TABLES = ("recovered_series", "fit_results", "recovery_edges")


def _query(sql: str, params: list | None = None) -> list[tuple]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql, params or []).fetchall()
    finally:
        con.close()


def _parse_report(text: str) -> dict[int, dict]:
    jobs: dict[int, dict] = {}
    current: int | None = None
    for line in text.splitlines():
        stripped = line.strip()
        header = re.match(r"job (\d+):", stripped)
        if header:
            current = int(header.group(1))
            jobs[current] = {}
            continue
        if current is None:
            continue
        if stripped.startswith("frequency_hz"):
            jobs[current]["frequency_hz"] = float(stripped.split("=")[1])
        elif stripped.startswith("decay_per_second"):
            jobs[current]["decay_per_second"] = float(stripped.split("=")[1])
        elif stripped.startswith("rejected_frames"):
            jobs[current]["rejected_frames"] = int(stripped.split("=")[1])
    return jobs


def _count_dot_nodes(dot_text: str) -> int:
    node_attr = "[" + "label" + "="
    edge_token = "-" + ">"
    return sum(
        1
        for line in dot_text.splitlines()
        if node_attr in line and edge_token not in line.split("[", 1)[0]
    )


@pytest.fixture(scope="session")
def driver_run():
    assert DRIVER.is_file(), f"agent did not create the driver at {DRIVER}"
    assert PRISTINE_DB.is_file(), f"missing pristine seed database {PRISTINE_DB}"

    shutil.copy(PRISTINE_DB, DB_PATH)

    pending = _query("SELECT COUNT(*) FROM jobs WHERE status = 'pending'")[0][0]
    assert pending == NUM_JOBS, f"expected {NUM_JOBS} pending jobs after restore, got {pending}"

    proc = subprocess.run(
        ["python3", DRIVER.name],
        cwd=str(APP),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"recover_motion.py exited {proc.returncode}\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    return proc


@pytest.fixture(scope="session")
def report_text(driver_run):
    proc = subprocess.run(
        ["python3", str(REPORT_SCRIPT)],
        cwd=str(APP),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"report.py failed:\n{proc.stderr}"
    return proc.stdout


def test_populates_output_tables(driver_run):
    """Verify the driver creates and fills all required output tables."""
    tables = {row[0] for row in _query("SELECT table_name FROM information_schema.tables")}
    for table in OUTPUT_TABLES:
        assert table in tables, f"driver did not create output table {table!r}"

    for table in OUTPUT_TABLES:
        job_ids = {row[0] for row in _query(f"SELECT DISTINCT job_id FROM {table}")}
        assert set(JOB_IDS).issubset(job_ids), (
            f"{table} missing rows for jobs {set(JOB_IDS) - job_ids}"
        )

    fit_ids = sorted(row[0] for row in _query("SELECT job_id FROM fit_results"))
    assert fit_ids == JOB_IDS, f"fit_results must hold exactly one row per job; got job_ids {fit_ids}"


def test_jobs_marked_processed(driver_run):
    """Verify every queued job reaches the done terminal state."""
    statuses = [row[0] for row in _query("SELECT status FROM jobs")]
    assert len(statuses) == NUM_JOBS, f"expected {NUM_JOBS} jobs, found {len(statuses)}"
    assert all(status != "pending" for status in statuses), (
        f"some jobs are still pending: {statuses}"
    )
    assert all(status == "done" for status in statuses), (
        f"every processed job must reach the 'done' terminal state; got {statuses}"
    )


def test_frequency_within_tolerance(driver_run):
    """Verify recovered natural frequencies stay within tolerance."""
    recovered = {
        job_id: freq
        for job_id, freq in _query("SELECT job_id, frequency_hz FROM fit_results")
    }
    assert set(recovered) == set(JOB_IDS), f"fit_results job coverage wrong: {sorted(recovered)}"
    for job_id, (freq_true, _decay_true) in GROUND_TRUTH.items():
        rel_err = abs(recovered[job_id] - freq_true) / freq_true
        assert rel_err <= FREQ_REL_TOL, (
            f"job {job_id}: recovered frequency {recovered[job_id]:.4f} Hz differs from "
            f"ground truth {freq_true} Hz by {rel_err:.3%} > {FREQ_REL_TOL:.0%}"
        )


def test_decay_within_tolerance(driver_run):
    """Verify recovered decay constants stay within tolerance."""
    recovered = {
        job_id: decay
        for job_id, decay in _query("SELECT job_id, decay_per_second FROM fit_results")
    }
    assert set(recovered) == set(JOB_IDS), f"fit_results job coverage wrong: {sorted(recovered)}"
    for job_id, (_freq_true, decay_true) in GROUND_TRUTH.items():
        rel_err = abs(recovered[job_id] - decay_true) / decay_true
        assert rel_err <= DECAY_REL_TOL, (
            f"job {job_id}: recovered decay {recovered[job_id]:.4f}/s differs from "
            f"ground truth {decay_true}/s by {rel_err:.3%} > {DECAY_REL_TOL:.0%}"
        )


def test_rejected_counts_match(driver_run):
    """Verify rejected-frame counts match the audit tables."""
    kinds = {row[0] for row in _query("SELECT DISTINCT kind FROM recovery_edges")}
    assert kinds <= {"accepted", "rejected"}, f"unexpected recovery_edges kinds: {kinds}"

    rejected_edges = dict(
        _query(
            "SELECT job_id, COUNT(*) FROM recovery_edges "
            "WHERE kind = 'rejected' GROUP BY job_id"
        )
    )
    for job_id, expected in EXPECTED_REJECTED.items():
        assert rejected_edges.get(job_id, 0) == expected, (
            f"job {job_id}: recovery_edges has {rejected_edges.get(job_id, 0)} rejected "
            f"segments, expected {expected}"
        )

    fit_rejected = dict(_query("SELECT job_id, rejected_frames FROM fit_results"))
    for job_id, expected in EXPECTED_REJECTED.items():
        assert fit_rejected.get(job_id) == expected, (
            f"job {job_id}: fit_results.rejected_frames = {fit_rejected.get(job_id)}, "
            f"expected {expected}"
        )


def test_graph_artifacts_emitted(driver_run):
    """Verify Graphviz DOT and SVG artifacts are emitted."""
    assert DOT_PATH.is_file() and DOT_PATH.stat().st_size > 0, f"missing/empty {DOT_PATH}"
    dot_text = DOT_PATH.read_text(encoding="utf-8")
    assert "digraph" in dot_text, "recovery_graph.dot is missing a digraph declaration"

    assert SVG_PATH.is_file() and SVG_PATH.stat().st_size > 0, f"missing/empty {SVG_PATH}"
    svg_text = SVG_PATH.read_text(encoding="utf-8")
    assert re.search(r"<svg\b", svg_text), "recovery_graph.svg is missing an svg root element"


def test_graph_node_count_matches_edges(driver_run):
    """Verify graph vertex count matches recovery_edges row count."""
    total_segments = _query("SELECT COUNT(*) FROM recovery_edges")[0][0]
    assert total_segments > 0, "recovery_edges is empty; nothing to document in the graph"

    dot_text = DOT_PATH.read_text(encoding="utf-8")
    node_count = _count_dot_nodes(dot_text)
    assert node_count == total_segments, (
        f"recovery_graph.dot has {node_count} vertices but recovery_edges records "
        f"{total_segments} segments; every accepted/rejected segment must be a vertex"
    )


def test_report_stdout_matches_snapshot(driver_run, report_text):
    """Verify report stdout matches database-derived summaries."""
    assert "PENDULUM RECOVERY REPORT" in report_text, "report header missing"
    jobs = _parse_report(report_text)
    assert set(jobs) == set(JOB_IDS), f"report covers jobs {sorted(jobs)}, expected {JOB_IDS}"

    for job_id, (freq_true, decay_true) in GROUND_TRUTH.items():
        entry = jobs[job_id]
        freq_err = abs(entry["frequency_hz"] - freq_true) / freq_true
        decay_err = abs(entry["decay_per_second"] - decay_true) / decay_true
        assert freq_err <= FREQ_REL_TOL, (
            f"job {job_id}: reported frequency {entry['frequency_hz']} off by {freq_err:.3%}"
        )
        assert decay_err <= DECAY_REL_TOL, (
            f"job {job_id}: reported decay {entry['decay_per_second']} off by {decay_err:.3%}"
        )
        assert entry["rejected_frames"] == EXPECTED_REJECTED[job_id], (
            f"job {job_id}: reported rejected_frames {entry['rejected_frames']}, "
            f"expected {EXPECTED_REJECTED[job_id]}"
        )

    total_segments = _query("SELECT COUNT(*) FROM recovery_edges")[0][0]
    dag_match = re.search(r"total_dag_nodes\s*=\s*(\d+)", report_text)
    assert dag_match and int(dag_match.group(1)) == total_segments, (
        f"total_dag_nodes in report does not equal recovery_edges row count ({total_segments})"
    )
    rejected_match = re.search(r"total_rejected_frames\s*=\s*(\d+)", report_text)
    assert rejected_match and int(rejected_match.group(1)) == sum(EXPECTED_REJECTED.values()), (
        f"total_rejected_frames should be {sum(EXPECTED_REJECTED.values())}"
    )
