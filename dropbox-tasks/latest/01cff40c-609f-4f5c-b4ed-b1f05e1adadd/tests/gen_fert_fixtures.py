"""Generate JSONL fertigation fixtures for verifier tests."""

from __future__ import annotations

import os
from pathlib import Path

from fertigation_expect import attach_line_crc, serialize_jsonl_line

BASE_TS = 1_714_502_400


def zone_prefix() -> str:
    run_id = os.environ.get("VERIFY_RUN_ID", "local")
    return f"b-{run_id[:8]}"


def test_zone_id() -> str:
    return "zone-a"


def write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = [attach_line_crc(line) for line in lines]
    path.write_text(
        "\n".join(serialize_jsonl_line(row) for row in stamped) + "\n",
        encoding="utf-8",
    )


def zone_register(zone_id: str, crop: str = "tomato", seq: int = 1) -> dict:
    return {
        "event_type": "ZONE_REGISTER",
        "event_seq": seq,
        "zone_id": zone_id,
        "crop_label": crop,
    }


def batch_open(zone_id: str, batch_id: str, opened_at: int, seq: int) -> dict:
    return {
        "event_type": "BATCH_OPEN",
        "event_seq": seq,
        "zone_id": zone_id,
        "batch_id": batch_id,
        "opened_at_unix": opened_at,
    }


def dose_tick(
    batch_id: str,
    ec: float,
    ph: float,
    volume: int,
    recorded_at: int,
    seq: int,
) -> dict:
    return {
        "event_type": "DOSE_TICK",
        "event_seq": seq,
        "batch_id": batch_id,
        "ec_mS": ec,
        "ph": ph,
        "volume_ml": volume,
        "recorded_at_unix": recorded_at,
    }


def batch_close(batch_id: str, closed_at: int, seq: int) -> dict:
    return {
        "event_type": "BATCH_CLOSE",
        "event_seq": seq,
        "batch_id": batch_id,
        "closed_at_unix": closed_at,
    }


def compliant_batch_flow(zone_id: str, batch_id: str, base: int) -> list[dict]:
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch_id, base, seq=2),
        dose_tick(batch_id, 2.0, 6.0, 500, base + 10, seq=3),
        dose_tick(batch_id, 2.0, 6.0, 500, base + 20, seq=4),
        batch_close(batch_id, base + 100, seq=5),
    ]


def public_sample_events() -> list[dict]:
    zone = "zone-a"
    batch = "batch-public-1"
    base = BASE_TS
    return [
        zone_register(zone, seq=1),
        batch_open(zone, batch, base, seq=2),
        dose_tick(batch, 2.0, 6.0, 500, base + 10, seq=3),
        dose_tick(batch, 2.0, 6.0, 500, base + 20, seq=4),
        batch_close(batch, base + 100, seq=5),
    ]


def ec_spike_events(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-ec-spike"
    t0 = BASE_TS + 30_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch, t0, seq=2),
        dose_tick(batch, 2.0, 6.0, 400, t0 + 10, seq=3),
        dose_tick(batch, 12.0, 6.0, 400, t0 + 610, seq=4),
        dose_tick(batch, 2.0, 6.0, 400, t0 + 1210, seq=5),
        batch_close(batch, t0 + 1300, seq=6),
    ]


def ph_outlier_events(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-ph-out"
    t0 = BASE_TS + 40_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch, t0, seq=2),
        dose_tick(batch, 2.0, 6.0, 400, t0 + 10, seq=3),
        dose_tick(batch, 2.0, 6.0, 400, t0 + 110, seq=4),
        dose_tick(batch, 2.0, 4.5, 400, t0 + 210, seq=5),
        batch_close(batch, t0 + 300, seq=6),
    ]


def volume_per_batch_events(zone_id: str) -> list[dict]:
    batch_a = f"{zone_id}-vol-a"
    batch_b = f"{zone_id}-vol-b"
    base = BASE_TS + 10_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch_a, base, seq=2),
        dose_tick(batch_a, 2.0, 6.0, 3000, base + 10, seq=3),
        dose_tick(batch_a, 2.0, 6.0, 1500, base + 20, seq=4),
        batch_close(batch_a, base + 100, seq=5),
        batch_open(zone_id, batch_b, base + 200, seq=6),
        dose_tick(batch_b, 2.0, 6.0, 3000, base + 210, seq=7),
        dose_tick(batch_b, 2.0, 6.0, 1500, base + 220, seq=8),
        batch_close(batch_b, base + 300, seq=9),
    ]


def daily_volume_events(zone_id: str) -> list[dict]:
    batch_a = f"{zone_id}-day-a"
    batch_b = f"{zone_id}-day-b"
    day_base = BASE_TS + 20_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch_a, day_base, seq=2),
        dose_tick(batch_a, 2.0, 6.0, 4500, day_base + 10, seq=3),
        dose_tick(batch_a, 2.0, 6.0, 500, day_base + 20, seq=4),
        batch_close(batch_a, day_base + 100, seq=5),
        batch_open(zone_id, batch_b, day_base + 200, seq=6),
        dose_tick(batch_b, 2.0, 6.0, 4500, day_base + 210, seq=7),
        dose_tick(batch_b, 2.0, 6.0, 500, day_base + 220, seq=8),
        batch_close(batch_b, day_base + 300, seq=9),
    ]


def min_dose_fail_events(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-min-dose"
    base = BASE_TS + 5_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch, base, seq=2),
        dose_tick(batch, 2.0, 6.0, 500, base + 10, seq=3),
        batch_close(batch, base + 100, seq=4),
    ]


def export_closed_only_events(zone_a: str, zone_b: str) -> list[dict]:
    open_batch = f"{zone_a}-open"
    closed_batch = f"{zone_b}-closed"
    return [
        zone_register(zone_a, seq=1),
        zone_register(zone_b, seq=2),
        batch_open(zone_a, open_batch, BASE_TS, seq=3),
        dose_tick(open_batch, 2.0, 6.0, 500, BASE_TS + 5, seq=4),
        batch_open(zone_b, closed_batch, BASE_TS + 1000, seq=5),
        dose_tick(closed_batch, 2.0, 6.0, 500, BASE_TS + 1010, seq=6),
        dose_tick(closed_batch, 2.0, 6.0, 500, BASE_TS + 1020, seq=7),
        batch_close(closed_batch, BASE_TS + 1100, seq=8),
    ]


def shuffled_dose_seq_events(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-shuffle"
    t0 = BASE_TS + 50_100
    lines = [
        dose_tick(batch, 2.0, 6.0, 400, t0, seq=3),
        dose_tick(batch, 12.0, 6.0, 400, t0 + 600, seq=4),
        dose_tick(batch, 2.0, 6.0, 400, t0 + 1200, seq=5),
    ]
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch, BASE_TS + 50_000, seq=2),
        lines[1],
        lines[0],
        lines[2],
        batch_close(batch, t0 + 1300, seq=6),
    ]


def leadin_events(zone_id: str) -> list[dict]:
    prior = f"{zone_id}-prior"
    new = f"{zone_id}-new"
    day_open = BASE_TS + 60_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, prior, day_open, seq=2),
        dose_tick(prior, 20.0, 6.0, 400, day_open + 60, seq=3),
        dose_tick(prior, 20.0, 6.0, 400, day_open + 120, seq=4),
        batch_close(prior, day_open + 200, seq=5),
        batch_open(zone_id, new, day_open + 400, seq=6),
        dose_tick(new, 2.0, 6.0, 400, day_open + 1000, seq=7),
        dose_tick(new, 2.0, 6.0, 400, day_open + 1600, seq=8),
        batch_close(new, day_open + 1700, seq=9),
    ]


def cross_run_part_a(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-cross-a"
    day_base = BASE_TS + 70_000
    return [
        zone_register(zone_id, seq=1),
        batch_open(zone_id, batch, day_base, seq=2),
        dose_tick(batch, 2.0, 6.0, 4500, day_base + 10, seq=3),
        dose_tick(batch, 2.0, 6.0, 500, day_base + 20, seq=4),
        batch_close(batch, day_base + 100, seq=5),
    ]


def cross_run_part_b(zone_id: str) -> list[dict]:
    batch = f"{zone_id}-cross-b"
    day_base = BASE_TS + 70_000
    return [
        batch_open(zone_id, batch, day_base + 200, seq=1),
        dose_tick(batch, 2.0, 6.0, 4500, day_base + 210, seq=2),
        dose_tick(batch, 2.0, 6.0, 500, day_base + 220, seq=3),
        batch_close(batch, day_base + 300, seq=4),
    ]


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    public_out = root / "environment" / "app" / "fixtures" / "public" / "sample_events.jsonl"
    write_jsonl(public_out, public_sample_events())
    print(f"wrote {public_out}")
    hidden_out = Path(__file__).resolve().parent / "fixtures" / "hidden" / "shuffled_leadin.jsonl"
    hidden_out.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(hidden_out, shuffled_dose_seq_events("zone-a"))
    print(f"wrote {hidden_out}")
