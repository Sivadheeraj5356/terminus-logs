"""Read-only recovery report.

Snapshots the recovery worker's output tables (recovered_series, fit_results,
recovery_edges) into a deterministic human-readable summary printed to stdout:

  * recovered natural frequency and decay/damping constant per job,
  * per-job rejected-frame counts,
  * a summary of the Graphviz recovery-DAG nodes.

All floating-point values are rounded to REPORT_DECIMAL_PLACES so the stdout
snapshot is byte-stable. The database connection is opened read-only; this tool
never creates, alters, or deletes any table or row.

Usage::

    python report.py [--db pendulum_captures.duckdb]
"""

from __future__ import annotations

import argparse

import duckdb

DB_FILENAME = "pendulum_captures.duckdb"
REPORT_DECIMAL_PLACES = 3

_OUTPUT_TABLES = ("recovered_series", "fit_results", "recovery_edges")


def _fmt(value: float) -> str:
    """Round a float to the pinned precision for deterministic output."""

    return f"{round(float(value), REPORT_DECIMAL_PLACES):.{REPORT_DECIMAL_PLACES}f}"


def _load_fit_results(con: duckdb.DuckDBPyConnection):
    return con.execute(
        """
        SELECT job_id, frequency_hz, decay_per_second, rejected_frames
        FROM fit_results
        ORDER BY job_id
        """
    ).fetchall()


def _load_series_counts(con: duckdb.DuckDBPyConnection):
    rows = con.execute(
        """
        SELECT job_id, COUNT(*) AS accepted_frames
        FROM recovered_series
        GROUP BY job_id
        ORDER BY job_id
        """
    ).fetchall()
    return {job_id: accepted for job_id, accepted in rows}


def _load_node_summary(con: duckdb.DuckDBPyConnection):
    rows = con.execute(
        """
        SELECT job_id,
               SUM(CASE WHEN kind = 'accepted' THEN 1 ELSE 0 END) AS accepted_nodes,
               SUM(CASE WHEN kind = 'rejected' THEN 1 ELSE 0 END) AS rejected_nodes,
               COUNT(*) AS total_nodes
        FROM recovery_edges
        GROUP BY job_id
        ORDER BY job_id
        """
    ).fetchall()
    return {
        job_id: (int(accepted or 0), int(rejected or 0), int(total or 0))
        for job_id, accepted, rejected, total in rows
    }


def render_report(con: duckdb.DuckDBPyConnection) -> str:
    """Build the deterministic report text from the output tables."""

    fits = _load_fit_results(con)
    accepted_counts = _load_series_counts(con)
    node_summary = _load_node_summary(con)

    lines = []
    lines.append("PENDULUM RECOVERY REPORT")
    lines.append("=" * 40)

    total_nodes = 0
    total_rejected = 0
    for job_id, frequency, decay, rejected in fits:
        accepted = accepted_counts.get(job_id, 0)
        acc_nodes, rej_nodes, job_nodes = node_summary.get(job_id, (0, 0, 0))
        total_nodes += job_nodes
        total_rejected += int(rejected)
        lines.append(f"job {job_id}:")
        lines.append(f"  frequency_hz     = {_fmt(frequency)}")
        lines.append(f"  decay_per_second = {_fmt(decay)}")
        lines.append(f"  rejected_frames  = {int(rejected)}")
        lines.append(f"  accepted_frames  = {int(accepted)}")
        lines.append(
            f"  dag_nodes        = {job_nodes} "
            f"(accepted={acc_nodes}, rejected={rej_nodes})"
        )

    lines.append("-" * 40)
    lines.append(f"total_jobs           = {len(fits)}")
    lines.append(f"total_rejected_frames = {total_rejected}")
    lines.append(f"total_dag_nodes       = {total_nodes}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only snapshot of the pendulum recovery results."
    )
    parser.add_argument(
        "--db",
        default=DB_FILENAME,
        help=f"database path (default: {DB_FILENAME})",
    )
    args = parser.parse_args()

    # read_only=True opens the database without write access.
    con = duckdb.connect(args.db, read_only=True)
    try:
        print(render_report(con))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
