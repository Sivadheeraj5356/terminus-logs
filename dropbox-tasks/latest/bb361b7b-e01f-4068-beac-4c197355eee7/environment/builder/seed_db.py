"""Build the seeded pendulum-recovery job database.

Running ``python seed_db.py`` (no arguments) writes ``pendulum_captures.duckdb``
into the project working directory containing:

  * a ``jobs`` queue table with NUM_RECOVERY_JOBS pending jobs, and
  * a ``frame_strips`` table holding one PNG frame-strip BLOB per job.

The database is deterministic: given the pinned constants in ``frame_synth`` it is
byte-stable across builds. Ground-truth oscillation parameters used to render the
frames are never written to any table.
"""

from __future__ import annotations

import argparse
import os

import duckdb

import frame_synth
from frame_synth import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    FRAMES_PER_STRIP,
    NUM_RECOVERY_JOBS,
)

DB_FILENAME = "pendulum_captures.duckdb"

_JOB_LABELS = {
    1: "west-atrium-capture",
    2: "north-gallery-capture",
    3: "loading-dock-capture",
    4: "rooftop-rig-capture",
}


def _create_input_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE jobs (
            job_id       INTEGER PRIMARY KEY,
            label        VARCHAR NOT NULL,
            frames_total INTEGER NOT NULL,
            frame_width  INTEGER NOT NULL,
            frame_height INTEGER NOT NULL,
            status       VARCHAR NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE frame_strips (
            job_id    INTEGER PRIMARY KEY,
            png_blob  BLOB NOT NULL,
            byte_size INTEGER NOT NULL
        )
        """
    )


def _seed(con: duckdb.DuckDBPyConnection) -> None:
    strips = frame_synth.synthesize_all()
    if len(strips) != NUM_RECOVERY_JOBS:
        raise RuntimeError(
            f"expected {NUM_RECOVERY_JOBS} strips, synthesized {len(strips)}"
        )

    for strip in strips:
        label = _JOB_LABELS.get(strip.job_id, f"capture-{strip.job_id}")
        con.execute(
            "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)",
            [
                strip.job_id,
                label,
                FRAMES_PER_STRIP,
                FRAME_WIDTH,
                FRAME_HEIGHT,
                "pending",
            ],
        )
        con.execute(
            "INSERT INTO frame_strips VALUES (?, ?, ?)",
            [strip.job_id, strip.png_bytes, len(strip.png_bytes)],
        )


def build_database(db_path: str) -> None:
    """Create ``db_path`` fresh with the seeded input tables."""

    if os.path.exists(db_path):
        os.remove(db_path)
    con = duckdb.connect(db_path)
    try:
        _create_input_tables(con)
        _seed(con)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the seeded pendulum-recovery DuckDB database."
    )
    parser.add_argument(
        "--db",
        default=DB_FILENAME,
        help=f"output database path (default: {DB_FILENAME})",
    )
    args = parser.parse_args()
    build_database(args.db)
    print(f"wrote {args.db} with {NUM_RECOVERY_JOBS} pending jobs")


if __name__ == "__main__":
    main()
