#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > recover_motion.py <<'PY'
#!/usr/bin/env python3
"""Pendulum motion solver: decode montages, track bob, fit damped oscillation."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import duckdb
import graphviz
import numpy as np
from PIL import Image
from scipy.optimize import curve_fit

DB_PATH = Path("pendulum_captures.duckdb")
DOT_PATH = Path("recovery_graph.dot")
SVG_PATH = Path("recovery_graph.svg")
FRAME_INTERVAL_SECONDS = 0.05


def is_clean_frame(cell: np.ndarray) -> bool:
    background = float(np.median(cell))
    dark_pixels = int((cell < 80).sum())
    near_background = abs(int(background) - 235) < 20
    has_bob = 10 < dark_pixels < 400
    return near_background and has_bob


def decode_strip(png_bytes: bytes, frame_width: int, frame_height: int, frames_total: int) -> np.ndarray:
    arr = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("L"))
    if arr.shape != (frame_height, frame_width * frames_total):
        raise ValueError(f"unexpected montage shape {arr.shape}")
    return arr


def track_frame(cell: np.ndarray) -> float | None:
    if not is_clean_frame(cell):
        return None
    _, xcoords = np.where(cell < 80)
    return float(xcoords.mean() - cell.shape[1] / 2.0)


def damped_model(t, amplitude, decay, frequency, phase):
    return amplitude * np.exp(-decay * t) * np.cos(2 * np.pi * frequency * t + phase)


def ensure_output_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS recovered_series (
            job_id       INTEGER NOT NULL,
            frame_index  INTEGER NOT NULL,
            t_seconds    DOUBLE  NOT NULL,
            angle        DOUBLE  NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS fit_results (
            job_id             INTEGER PRIMARY KEY,
            frequency_hz       DOUBLE NOT NULL,
            decay_per_second   DOUBLE NOT NULL,
            rejected_frames    INTEGER NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_edges (
            job_id        INTEGER NOT NULL,
            node_id       VARCHAR NOT NULL,
            kind          VARCHAR NOT NULL,
            frame_index   INTEGER NOT NULL
        )
        """
    )


def process_job(
    con: duckdb.DuckDBPyConnection,
    job_id: int,
    frame_width: int,
    frame_height: int,
    frames_total: int,
    png_bytes: bytes,
) -> None:
    montage = decode_strip(png_bytes, frame_width, frame_height, frames_total)
    accepted_ts: list[float] = []
    accepted_angles: list[float] = []
    rejected = 0
    edges: list[tuple[int, str, str, int]] = []

    for frame_index in range(frames_total):
        col = frame_index * frame_width
        cell = montage[:, col : col + frame_width]
        angle = track_frame(cell)
        node_id = f"j{job_id}_f{frame_index}"
        if angle is None:
            rejected += 1
            kind = "rejected"
        else:
            kind = "accepted"
            t_seconds = frame_index * FRAME_INTERVAL_SECONDS
            accepted_ts.append(t_seconds)
            accepted_angles.append(angle)
            con.execute(
                "INSERT INTO recovered_series VALUES (?, ?, ?, ?)",
                [job_id, frame_index, t_seconds, angle],
            )
        edges.append((job_id, node_id, kind, frame_index))

    if len(accepted_ts) < 4:
        raise RuntimeError(f"job {job_id}: insufficient accepted frames for fitting")

    ts = np.array(accepted_ts)
    angles = np.array(accepted_angles)
    p0 = [angles.max() - angles.min(), 0.5, 1.0, 0.0]
    params, _ = curve_fit(
        damped_model,
        ts,
        angles,
        p0=p0,
        maxfev=20000,
        bounds=([0.0, 0.0, 0.01, -np.pi], [np.inf, 10.0, 5.0, np.pi]),
    )
    _amplitude, decay, frequency, _phase = params
    frequency_hz = abs(float(frequency))
    decay_per_second = abs(float(decay))

    con.execute(
        "INSERT INTO fit_results VALUES (?, ?, ?, ?)",
        [job_id, frequency_hz, decay_per_second, rejected],
    )
    for row in edges:
        con.execute("INSERT INTO recovery_edges VALUES (?, ?, ?, ?)", list(row))

    con.execute(
        "UPDATE jobs SET status = 'done' WHERE job_id = ?",
        [job_id],
    )


def build_graph(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        """
        SELECT job_id, node_id, kind, frame_index
        FROM recovery_edges
        ORDER BY job_id, frame_index
        """
    ).fetchall()
    dot = graphviz.Digraph("recovery")
    prev: dict[int, str] = {}
    for job_id, node_id, kind, frame_index in rows:
        label = f"{node_id}\\n{kind}"
        dot.node(node_id, label=label)
        if job_id in prev:
            dot.edge(prev[job_id], node_id)
        prev[job_id] = node_id
    dot.save(str(DOT_PATH))
    subprocess.run(
        ["dot", "-Tsvg", str(DOT_PATH), "-o", str(SVG_PATH)],
        check=True,
    )


def main() -> int:
    con = duckdb.connect(str(DB_PATH))
    try:
        ensure_output_tables(con)
        jobs = con.execute(
            """
            SELECT j.job_id, j.frames_total, j.frame_width, j.frame_height, f.png_blob
            FROM jobs j
            JOIN frame_strips f ON j.job_id = f.job_id
            WHERE j.status = 'pending'
            ORDER BY j.job_id
            """
        ).fetchall()
        for job_id, frames_total, frame_width, frame_height, png_blob in jobs:
            process_job(
                con,
                int(job_id),
                int(frame_width),
                int(frame_height),
                int(frames_total),
                bytes(png_blob),
            )
        build_graph(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

chmod +x recover_motion.py
python3 recover_motion.py
