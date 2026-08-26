"""Tests for the seeded job database produced by the generator.

Covers the environment-side acceptance criteria:
  * generator produces jobs (~4 pending) + one PNG BLOB per job,
  * each BLOB decodes to a damped-oscillation frame sequence,
  * a deterministic subset of frames per job is degraded and rejectable,
  * ground-truth oscillation parameters are absent from every table.
"""

from io import BytesIO

import duckdb
import numpy as np
from PIL import Image
from scipy.optimize import curve_fit

import frame_synth as fs


def _decode_frames(png_bytes):
    arr = np.asarray(Image.open(BytesIO(bytes(png_bytes))).convert("L"))
    n = arr.shape[1] // fs.FRAME_WIDTH
    return arr, n


def _is_clean_frame(cell):
    background = np.median(cell)
    dark_pixels = int((cell < 80).sum())
    near_background = abs(int(background) - fs.BACKGROUND_LEVEL) < 20
    has_bob = 10 < dark_pixels < 400
    return near_background and has_bob


def _rejected_indices(arr, n):
    rejected = []
    for i in range(n):
        cell = arr[:, i * fs.FRAME_WIDTH : (i + 1) * fs.FRAME_WIDTH]
        if not _is_clean_frame(cell):
            rejected.append(i)
    return rejected


def _tracked_series(arr, n):
    ts, xs = [], []
    for i in range(n):
        cell = arr[:, i * fs.FRAME_WIDTH : (i + 1) * fs.FRAME_WIDTH]
        if not _is_clean_frame(cell):
            continue
        _, xcoords = np.where(cell < 80)
        ts.append(i * fs.FRAME_INTERVAL_SECONDS)
        xs.append(xcoords.mean() - fs.FRAME_WIDTH / 2.0)
    return np.array(ts), np.array(xs)


def test_jobs_table_has_four_pending_jobs(seeded_db):
    con = duckdb.connect(seeded_db, read_only=True)
    try:
        rows = con.execute(
            "SELECT job_id, status FROM jobs ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == fs.NUM_RECOVERY_JOBS
    assert all(status == "pending" for _, status in rows)
    assert [job_id for job_id, _ in rows] == list(range(1, fs.NUM_RECOVERY_JOBS + 1))


def test_one_png_blob_per_job(seeded_db):
    con = duckdb.connect(seeded_db, read_only=True)
    try:
        rows = con.execute(
            "SELECT job_id, png_blob, byte_size FROM frame_strips ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == fs.NUM_RECOVERY_JOBS
    for job_id, blob, byte_size in rows:
        data = bytes(blob)
        assert byte_size == len(data)
        # PNG magic number.
        assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_blob_decodes_to_correct_frame_count(seeded_db):
    con = duckdb.connect(seeded_db, read_only=True)
    try:
        rows = con.execute(
            "SELECT job_id, png_blob FROM frame_strips ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()
    for _, blob in rows:
        arr, n = _decode_frames(blob)
        assert arr.shape[0] == fs.FRAME_HEIGHT
        assert n == fs.FRAMES_PER_STRIP


def test_frames_trace_recoverable_damped_oscillation(seeded_db):
    con = duckdb.connect(seeded_db, read_only=True)
    try:
        rows = con.execute(
            "SELECT job_id, png_blob FROM frame_strips ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()

    def model(t, amplitude, decay, frequency, phase):
        return amplitude * np.exp(-decay * t) * np.cos(2 * np.pi * frequency * t + phase)

    ground_truth = {p.job_id: p for p in fs.ground_truth_parameters()}
    for job_id, blob in rows:
        arr, n = _decode_frames(blob)
        ts, xs = _tracked_series(arr, n)
        gt = ground_truth[job_id]
        params, _ = curve_fit(
            model,
            ts,
            xs,
            p0=[xs.max(), gt.decay_per_second, gt.frequency_hz, 0.0],
            maxfev=20000,
        )
        recovered_frequency = abs(params[2])
        recovered_decay = abs(params[1])
        freq_rel_err = abs(recovered_frequency - gt.frequency_hz) / gt.frequency_hz
        decay_rel_err = abs(recovered_decay - gt.decay_per_second) / gt.decay_per_second
        # Comfortably inside the verifier tolerances (0.05 freq / 0.1 decay).
        assert freq_rel_err < 0.05
        assert decay_rel_err < 0.1


def test_degraded_frame_counts_are_deterministic_and_rejectable(seeded_db):
    con = duckdb.connect(seeded_db, read_only=True)
    try:
        rows = con.execute(
            "SELECT job_id, png_blob FROM frame_strips ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()
    for job_id, blob in rows:
        arr, n = _decode_frames(blob)
        rejected = _rejected_indices(arr, n)
        expected = fs.DEGRADED_FRAMES_PER_JOB[job_id - 1]
        assert len(rejected) == expected
        # Detected rejects match the generator's degraded indices exactly.
        strip = fs.synthesize_strip(
            fs.ground_truth_parameters()[job_id - 1], job_id - 1
        )
        assert rejected == strip.degraded_frame_indices


def test_database_is_byte_stable_across_builds(tmp_path):
    import hashlib

    import seed_db

    def blob_hashes(path):
        con = duckdb.connect(path, read_only=True)
        try:
            rows = con.execute(
                "SELECT job_id, png_blob FROM frame_strips ORDER BY job_id"
            ).fetchall()
        finally:
            con.close()
        return {
            job_id: hashlib.sha256(bytes(blob)).hexdigest() for job_id, blob in rows
        }

    first = str(tmp_path / "first.duckdb")
    second = str(tmp_path / "second.duckdb")
    seed_db.build_database(first)
    seed_db.build_database(second)
    assert blob_hashes(first) == blob_hashes(second)


def test_ground_truth_parameters_absent_from_all_tables(seeded_db):
    ground_truth_values = set()
    for params in fs.ground_truth_parameters():
        ground_truth_values.update(
            [params.frequency_hz, params.decay_per_second, params.amplitude_fraction]
        )

    con = duckdb.connect(seeded_db, read_only=True)
    try:
        table_names = [
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables"
            ).fetchall()
        ]
        for table in table_names:
            for row in con.execute(f'SELECT * FROM "{table}"').fetchall():
                for cell in row:
                    if isinstance(cell, (int, float)):
                        assert float(cell) not in ground_truth_values, (
                            f"ground-truth value {cell} leaked into {table}"
                        )
    finally:
        con.close()
