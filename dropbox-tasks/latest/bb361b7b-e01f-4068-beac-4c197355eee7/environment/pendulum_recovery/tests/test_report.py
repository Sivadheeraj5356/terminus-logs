"""Tests for the read-only report CLI.

Covers the report-side acceptance criteria:
  * report.py, run against a database that already contains the three output
    tables, prints recovered frequency, damping coefficient, per-job
    rejected-frame counts, and Graphviz DAG summaries, floats rounded to
    report_decimal_places,
  * report.py is strictly read-only.
"""

import shutil
import subprocess
import sys

import duckdb
import pytest

import report


def _add_output_tables(db_path):
    """Populate synthetic recovered_series/fit_results/recovery_edges."""

    con = duckdb.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE recovered_series("
            "job_id INTEGER, frame_index INTEGER, t_seconds DOUBLE, angle DOUBLE)"
        )
        con.execute(
            "CREATE TABLE fit_results("
            "job_id INTEGER PRIMARY KEY, frequency_hz DOUBLE, "
            "decay_per_second DOUBLE, rejected_frames INTEGER)"
        )
        con.execute(
            "CREATE TABLE recovery_edges("
            "job_id INTEGER, node_id VARCHAR, kind VARCHAR, "
            "frame_start INTEGER, frame_end INTEGER)"
        )
        fits = [
            (1, 0.90123, 0.34981, 5),
            (2, 1.29994, 0.55014, 7),
            (3, 1.75021, 0.79983, 6),
            (4, 2.20115, 1.10234, 8),
        ]
        for job_id, frequency, decay, rejected in fits:
            con.execute(
                "INSERT INTO fit_results VALUES (?, ?, ?, ?)",
                [job_id, frequency, decay, rejected],
            )
            for frame_index in range(48 - rejected):
                con.execute(
                    "INSERT INTO recovered_series VALUES (?, ?, ?, ?)",
                    [job_id, frame_index, frame_index * 0.05, 0.0],
                )
            con.execute(
                "INSERT INTO recovery_edges VALUES (?, ?, ?, ?, ?)",
                [job_id, f"accepted-{job_id}", "accepted", 0, 47],
            )
            con.execute(
                "INSERT INTO recovery_edges VALUES (?, ?, ?, ?, ?)",
                [job_id, f"rejected-{job_id}", "rejected", 0, 47],
            )
    finally:
        con.close()


@pytest.fixture
def db_with_outputs(seeded_db, tmp_path):
    db_path = str(tmp_path / "with_outputs.duckdb")
    shutil.copy(seeded_db, db_path)
    _add_output_tables(db_path)
    return db_path


def test_report_prints_expected_fields(db_with_outputs):
    con = duckdb.connect(db_with_outputs, read_only=True)
    try:
        text = report.render_report(con)
    finally:
        con.close()

    # Frequencies and decays rounded to 3 decimals.
    assert "frequency_hz     = 0.901" in text
    assert "decay_per_second = 0.350" in text
    assert "frequency_hz     = 2.201" in text
    assert "decay_per_second = 1.102" in text
    # Per-job rejected-frame counts (exact integers).
    assert "rejected_frames  = 5" in text
    assert "rejected_frames  = 8" in text
    # Graphviz DAG node summary.
    assert "dag_nodes        = 2 (accepted=1, rejected=1)" in text
    assert "total_dag_nodes       = 8" in text
    assert "total_rejected_frames = 26" in text


def test_report_floats_rounded_to_report_decimal_places(db_with_outputs):
    con = duckdb.connect(db_with_outputs, read_only=True)
    try:
        text = report.render_report(con)
    finally:
        con.close()
    for line in text.splitlines():
        if "frequency_hz" in line or "decay_per_second" in line:
            value = line.split("=")[1].strip()
            fractional = value.split(".")[1]
            assert len(fractional) == report.REPORT_DECIMAL_PLACES


def test_report_output_is_deterministic(db_with_outputs):
    con = duckdb.connect(db_with_outputs, read_only=True)
    try:
        first = report.render_report(con)
        second = report.render_report(con)
    finally:
        con.close()
    assert first == second


def test_report_cli_runs_with_db_flag(db_with_outputs):
    project_root = report.__file__.rsplit("/", 1)[0]
    result = subprocess.run(
        [sys.executable, "report.py", "--db", db_with_outputs],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "PENDULUM RECOVERY REPORT" in result.stdout


def test_report_is_read_only(db_with_outputs):
    con = duckdb.connect(db_with_outputs, read_only=True)
    try:
        before = {
            table: con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in ("jobs", "frame_strips", "recovered_series",
                          "fit_results", "recovery_edges")
        }
        report.render_report(con)
        after = {
            table: con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in before
        }
    finally:
        con.close()
    assert before == after


def test_report_connection_rejects_writes(db_with_outputs):
    con = duckdb.connect(db_with_outputs, read_only=True)
    try:
        with pytest.raises(Exception):
            con.execute("INSERT INTO fit_results VALUES (99, 1.0, 1.0, 0)")
    finally:
        con.close()
