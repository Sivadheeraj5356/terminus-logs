"""Greenhouse fertigation dose capture CLI verifier tests."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

from fertigation_expect import (
    attach_line_crc,
    expected_compliance,
    line_crc_for,
    serialize_jsonl_line,
)
from gen_fert_fixtures import (
    BASE_TS,
    batch_close,
    batch_open,
    compliant_batch_flow,
    cross_run_part_a,
    cross_run_part_b,
    daily_volume_events,
    dose_tick,
    ec_spike_events,
    export_closed_only_events,
    leadin_events,
    min_dose_fail_events,
    ph_outlier_events,
    shuffled_dose_seq_events,
    volume_per_batch_events,
    write_jsonl,
    zone_register,
)

INGEST = Path("/app/bin/fert-ingest")
EXPORT = Path("/app/bin/fert-export")
PUBLIC = Path("/app/fixtures/public/sample_events.jsonl")
PROFILE = Path("/app/config/greenhouse-profile.json")
COMPLIANCE_PATH = Path("/app/output/fertigation-compliance.json")
HIDDEN_SHUFFLED = (
    Path(__file__).resolve().parent / "fixtures" / "hidden" / "shuffled_leadin.jsonl"
)


def run_ingest(db: Path, events: Path) -> subprocess.CompletedProcess[str]:
    db.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [str(INGEST), "--db", str(db), "--events", str(events)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def run_export(db: Path, out: Path | None = None) -> subprocess.CompletedProcess[str]:
    target = out or COMPLIANCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [str(EXPORT), "--db", str(db), "--out", str(target)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def load_report(path: Path = COMPLIANCE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stderr_blob(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stderr + proc.stdout).lower()


def assert_stderr_contains(proc: subprocess.CompletedProcess[str], needle: str) -> None:
    assert needle.lower() in stderr_blob(proc), proc.stderr + proc.stdout


def ingest_events(db: Path, tmp_path: Path, events: list[dict], name: str) -> None:
    path = tmp_path / f"{name}.jsonl"
    write_jsonl(path, events)
    proc = run_ingest(db, path)
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_public_sample_jsonl_crc_spelling() -> None:
    """Public fixture uses integer JSON tokens (2, 6) and CRC matches line bytes."""
    raw = PUBLIC.read_text(encoding="utf-8")
    assert '"ec_mS":2.0' not in raw
    assert '"ph":6.0' not in raw
    for line in raw.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        assert line_crc_for(obj) == obj["line_crc"].upper()


def test_public_sample_ingest_export(tmp_path: Path) -> None:
    db = tmp_path / "public.db"
    out = tmp_path / "public-out.json"
    proc = run_ingest(db, PUBLIC)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    proc2 = run_export(db, out)
    assert proc2.returncode == 0, proc2.stderr + proc2.stdout
    written = load_report(out)
    expected = expected_compliance(db, PROFILE)
    assert written == expected
    assert written["summary"]["batch_count"] == 1


def test_idempotent_file_replay(tmp_path: Path) -> None:
    db = tmp_path / "idem.db"
    assert run_ingest(db, PUBLIC).returncode == 0
    n1 = connect(db).execute("SELECT COUNT(*) AS c FROM dose_events").fetchone()["c"]
    assert run_ingest(db, PUBLIC).returncode == 0
    n2 = connect(db).execute("SELECT COUNT(*) AS c FROM dose_events").fetchone()["c"]
    assert n1 == n2 == 2


def test_unknown_zone_open_rejected(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "unknown.db"
    path = tmp_path / "unknown.jsonl"
    write_jsonl(
        path,
        [
            batch_open("zone-unknown", f"{zone_id}-b", BASE_TS, seq=1),
        ],
    )
    proc = run_ingest(db, path)
    assert proc.returncode != 0
    assert_stderr_contains(proc, "unknown zone")


def test_batch_busy_blocks_second_open(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "busy.db"
    path = tmp_path / "busy.jsonl"
    write_jsonl(
        path,
        [
            zone_register(zone_id, seq=1),
            batch_open(zone_id, f"{zone_id}-b1", BASE_TS, seq=2),
            batch_open(zone_id, f"{zone_id}-b2", BASE_TS + 10, seq=3),
        ],
    )
    proc = run_ingest(db, path)
    assert proc.returncode != 0
    assert_stderr_contains(proc, "batch busy")
    conn = connect(db)
    try:
        open_count = conn.execute(
            "SELECT COUNT(*) AS c FROM fertigation_batches WHERE zone_id = ? AND status = 'OPEN'",
            (zone_id,),
        ).fetchone()["c"]
        assert open_count == 0
    finally:
        conn.close()


def test_ec_trapezoid_spike_fails_release(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "ec.db"
    ingest_events(db, tmp_path, ec_spike_events(zone_id), "ec")
    assert run_export(db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-ec-spike"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["ec_drift_integral"] > 5000
    assert row["ec_ok"] is False
    assert row["batch_release_ok"] is False


def test_ph_every_dose_not_average(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "ph.db"
    ingest_events(db, tmp_path, ph_outlier_events(zone_id), "ph")
    assert run_export(db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-ph-out"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["ph_ok"] is False


def test_volume_cap_per_batch_not_global(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "vol.db"
    ingest_events(db, tmp_path, volume_per_batch_events(zone_id), "vol")
    assert run_export(db).returncode == 0
    written = load_report()
    for suffix in ("vol-a", "vol-b"):
        batch_id = f"{zone_id}-{suffix}"
        row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
        assert row["volume_ok"] is True


def test_daily_volume_summed_on_close_same_local_day(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "daily.db"
    ingest_events(db, tmp_path, daily_volume_events(zone_id), "daily")
    assert run_export(db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-day-b"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["daily_volume_ok"] is False


def test_close_requires_min_dose_count(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "mindose.db"
    path = tmp_path / "mindose.jsonl"
    write_jsonl(path, min_dose_fail_events(zone_id))
    proc = run_ingest(db, path)
    assert proc.returncode != 0
    assert_stderr_contains(proc, "insufficient doses")


def test_close_clears_zone_state(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "close.db"
    batch_id = f"{zone_id}-close-ok"
    ingest_events(db, tmp_path, compliant_batch_flow(zone_id, batch_id, BASE_TS), "close")
    conn = connect(db)
    try:
        open_batch_id = conn.execute(
            "SELECT open_batch_id FROM zone_state WHERE zone_id = ?",
            (zone_id,),
        ).fetchone()["open_batch_id"]
        assert open_batch_id is None
        status_row = conn.execute(
            "SELECT status FROM fertigation_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()["status"]
        assert status_row == "CLOSED"
    finally:
        conn.close()
    path2 = tmp_path / "reopen.jsonl"
    write_jsonl(
        path2,
        [batch_open(zone_id, f"{zone_id}-reopen", BASE_TS + 200, seq=1)],
    )
    assert run_ingest(db, path2).returncode == 0


def test_export_closed_only_matches_expect(tmp_path: Path) -> None:
    db = tmp_path / "closed.db"
    zone_a = "zone-a"
    zone_b = "zone-b"
    ingest_events(db, tmp_path, export_closed_only_events(zone_a, zone_b), "closed")
    out = tmp_path / "closed-out.json"
    assert run_export(db, out).returncode == 0
    written = load_report(out)
    expected = expected_compliance(db, PROFILE)
    assert written == expected
    assert written["summary"]["batch_count"] == 1
    open_id = f"{zone_a}-open"
    assert all(b["batch_id"] != open_id for b in written["batches"])


def test_partial_fix_batch_open_only_still_fails_ec_trap(
    tmp_path: Path, zone_id: str
) -> None:
    db = tmp_path / "partial-ec.db"
    ingest_events(db, tmp_path, ec_spike_events(zone_id), "partial-ec")
    assert run_export(db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-ec-spike"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["ec_ok"] is False


def test_partial_fix_ph_average_only_fails_outlier_dose(
    tmp_path: Path, zone_id: str
) -> None:
    db = tmp_path / "partial-ph.db"
    ingest_events(db, tmp_path, ph_outlier_events(zone_id), "partial-ph")
    assert run_export(db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-ph-out"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["ph_ok"] is False
    assert row["batch_release_ok"] is False


def test_dose_log_event_seq_sort(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "shuffle.db"
    ingest_events(db, tmp_path, shuffled_dose_seq_events(zone_id), "shuffle")
    assert run_export(db).returncode == 0
    written = load_report()
    expected = expected_compliance(db, PROFILE)
    batch_id = f"{zone_id}-shuffle"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    exp_row = next(b for b in expected["batches"] if b["batch_id"] == batch_id)
    assert row["dose_count"] == 3
    assert row["ec_drift_integral"] == exp_row["ec_drift_integral"]
    assert row["ec_ok"] == exp_row["ec_ok"]


def test_ec_leadin_prior_batch_same_day(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "leadin.db"
    ingest_events(db, tmp_path, leadin_events(zone_id), "leadin")
    assert run_export(db).returncode == 0
    written = load_report()
    expected = expected_compliance(db, PROFILE)
    batch_id = f"{zone_id}-new"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    exp_row = next(b for b in expected["batches"] if b["batch_id"] == batch_id)
    assert row["ec_drift_integral"] == exp_row["ec_drift_integral"]
    assert row["ec_drift_integral"] > 2500
    assert row["ec_ok"] is False


def test_cross_run_shared_db_daily_volume(shared_db: Path, zone_id: str) -> None:
    ingest_events(shared_db, shared_db.parent, cross_run_part_a(zone_id), "cross-a")
    ingest_events(shared_db, shared_db.parent, cross_run_part_b(zone_id), "cross-b")
    assert run_export(shared_db).returncode == 0
    written = load_report()
    batch_id = f"{zone_id}-cross-b"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["daily_volume_ok"] is False


def test_compliance_hash_matches_expect(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "hash.db"
    batch_id = f"{zone_id}-hash"
    ingest_events(db, tmp_path, compliant_batch_flow(zone_id, batch_id, BASE_TS), "hash")
    out = tmp_path / "hash-out.json"
    assert run_export(db, out).returncode == 0
    written = load_report(out)
    expected = expected_compliance(db, PROFILE)
    assert written.get("compliance_hash") == expected["compliance_hash"]
    assert written == expected


def test_partial_fix_ingest_order_only_fails_ec_leadin(
    tmp_path: Path, zone_id: str
) -> None:
    db = tmp_path / "partial-leadin.db"
    prior = f"{zone_id}-prior"
    new = f"{zone_id}-new"
    day_open = BASE_TS + 80_000
    events = [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, prior, day_open, seq=2),
        dose_tick(prior, 20.0, 6.0, 400, day_open + 50, seq=3),
        dose_tick(prior, 20.0, 6.0, 400, day_open + 100, seq=4),
        batch_close(prior, day_open + 150, seq=5),
        batch_open(zone_id, new, day_open + 300, seq=6),
        dose_tick(new, 2.0, 6.0, 400, day_open + 900, seq=7),
        dose_tick(new, 2.0, 6.0, 400, day_open + 1500, seq=8),
        batch_close(new, day_open + 1600, seq=9),
    ]
    path = tmp_path / "partial-leadin.jsonl"
    stamped = [attach_line_crc(ev) for ev in events]
    # physical file order: swap dose lines (event_seq 8 before 7)
    ordered = stamped[:6] + [stamped[7], stamped[6]] + [stamped[8]]
    path.write_text(
        "\n".join(serialize_jsonl_line(row) for row in ordered) + "\n",
        encoding="utf-8",
    )
    proc = run_ingest(db, path)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert run_export(db).returncode == 0
    written = load_report()
    expected = expected_compliance(db, PROFILE)
    row = next(b for b in written["batches"] if b["batch_id"] == new)
    exp_row = next(b for b in expected["batches"] if b["batch_id"] == new)
    assert row["ec_drift_integral"] == exp_row["ec_drift_integral"]
    assert row["ec_ok"] is False


def test_bad_line_crc_aborts_ingest(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "crc.db"
    batch = f"{zone_id}-crc"
    path = tmp_path / "crc.jsonl"
    stamped = [
        attach_line_crc(zone_register(zone_id, seq=1)),
        attach_line_crc(batch_open(zone_id, batch, BASE_TS + 90_000, seq=2)),
        attach_line_crc(dose_tick(batch, 2.0, 6.0, 400, BASE_TS + 90_010, seq=3)),
        {**attach_line_crc(dose_tick(batch, 2.0, 6.0, 400, BASE_TS + 90_010, seq=3)), "line_crc": "FFFF"},
        attach_line_crc(dose_tick(batch, 2.0, 6.0, 400, BASE_TS + 90_020, seq=4)),
        attach_line_crc(batch_close(batch, BASE_TS + 90_100, seq=5)),
    ]
    path.write_text(
        "\n".join(serialize_jsonl_line(row) for row in stamped) + "\n",
        encoding="utf-8",
    )
    proc = run_ingest(db, path)
    assert proc.returncode != 0
    assert_stderr_contains(proc, "line_crc mismatch")
    conn = connect(db)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) AS c FROM dose_events WHERE batch_id = ?",
            (batch,),
        ).fetchone()["c"]
        assert cnt == 0
    finally:
        conn.close()


def test_non_increasing_recorded_at_rejected(tmp_path: Path, zone_id: str) -> None:
    db = tmp_path / "mono.db"
    batch = f"{zone_id}-mono"
    path = tmp_path / "mono.jsonl"
    write_jsonl(
        path,
        [
            zone_register(zone_id, seq=1),
            batch_open(zone_id, batch, BASE_TS, seq=2),
            dose_tick(batch, 2.0, 6.0, 500, BASE_TS + 100, seq=3),
            dose_tick(batch, 2.0, 6.0, 500, BASE_TS + 100, seq=4),
        ],
    )
    proc = run_ingest(db, path)
    assert proc.returncode != 0
    assert_stderr_contains(proc, "non-increasing recorded_at")


def test_hidden_shuffled_fixture(tmp_path: Path) -> None:
    assert HIDDEN_SHUFFLED.is_file(), f"missing bundled fixture {HIDDEN_SHUFFLED}"
    db = tmp_path / "hidden.db"
    out = tmp_path / "hidden-out.json"
    proc = run_ingest(db, HIDDEN_SHUFFLED)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert run_export(db, out).returncode == 0
    written = load_report(out)
    expected = expected_compliance(db, PROFILE)
    assert written == expected
    batch_id = "zone-a-shuffle"
    row = next(b for b in written["batches"] if b["batch_id"] == batch_id)
    assert row["dose_count"] == 3
    assert row["ec_ok"] is False
