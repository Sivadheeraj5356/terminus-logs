"""Independent compliance recompute for greenhouse fertigation verifier."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def load_profile(profile_path: Path) -> dict:
    return json.loads(profile_path.read_text(encoding="utf-8"))


def local_volume_date(unix_sec: int, tz_name: str) -> str:
    dt = datetime.fromtimestamp(unix_sec, tz=ZoneInfo(tz_name))
    return dt.strftime("%Y-%m-%d")


def _prior_closed_batch(
    conn: sqlite3.Connection,
    zone_id: str,
    opened_at_unix: int,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT batch_id, closed_at_unix FROM fertigation_batches
        WHERE zone_id = ? AND status = 'CLOSED' AND closed_at_unix IS NOT NULL
          AND closed_at_unix < ?
        ORDER BY closed_at_unix DESC LIMIT 1
        """,
        (zone_id, opened_at_unix),
    ).fetchone()


def _latest_dose_ec(conn: sqlite3.Connection, batch_id: str) -> float | None:
    row = conn.execute(
        """
        SELECT ec_mS FROM dose_events WHERE batch_id = ?
        ORDER BY recorded_at_unix DESC LIMIT 1
        """,
        (batch_id,),
    ).fetchone()
    return None if row is None else float(row["ec_mS"])


def lead_in_anchor_ec(
    conn: sqlite3.Connection,
    zone_id: str,
    opened_at_unix: int,
    target_ec: float,
    tz_name: str,
) -> float:
    prior = _prior_closed_batch(conn, zone_id, opened_at_unix)
    if prior is None or prior["closed_at_unix"] is None:
        return target_ec
    open_day = local_volume_date(opened_at_unix, tz_name)
    close_day = local_volume_date(int(prior["closed_at_unix"]), tz_name)
    if open_day != close_day:
        return target_ec
    ec = _latest_dose_ec(conn, prior["batch_id"])
    return target_ec if ec is None else ec


def ec_drift_integral(
    conn: sqlite3.Connection,
    doses: list[dict],
    opened_at_unix: int,
    zone_id: str,
    target_ec: float,
    tz_name: str,
) -> float:
    if not doses:
        return 0.0
    sorted_d = sorted(doses, key=lambda d: d["recorded_at_unix"])
    anchor = lead_in_anchor_ec(conn, zone_id, opened_at_unix, target_ec, tz_name)
    integral = 0.0
    first = sorted_d[0]
    dev_anchor = abs(anchor - target_ec)
    dev_first = abs(first["ec_mS"] - target_ec)
    lead_dt = first["recorded_at_unix"] - opened_at_unix
    if lead_dt > 0:
        integral += ((dev_anchor + dev_first) / 2) * lead_dt
    for i in range(len(sorted_d) - 1):
        cur = sorted_d[i]
        nxt = sorted_d[i + 1]
        dev_cur = abs(cur["ec_mS"] - target_ec)
        dev_nxt = abs(nxt["ec_mS"] - target_ec)
        dt = nxt["recorded_at_unix"] - cur["recorded_at_unix"]
        integral += ((dev_cur + dev_nxt) / 2) * dt
    return integral


def ph_ok(doses: list[dict], ph_min: float, ph_max: float) -> bool:
    if not doses:
        return False
    return all(ph_min <= d["ph"] <= ph_max for d in doses)


def batch_volume_ml(doses: list[dict]) -> int:
    return sum(int(d["volume_ml"]) for d in doses)


def closed_daily_volume_ml(
    conn: sqlite3.Connection,
    zone_id: str,
    volume_date: str,
    tz_name: str,
) -> int:
    rows = conn.execute(
        """
        SELECT batch_id, closed_at_unix FROM fertigation_batches
        WHERE zone_id = ? AND status = 'CLOSED' AND closed_at_unix IS NOT NULL
        """,
        (zone_id,),
    ).fetchall()
    total = 0
    for row in rows:
        if local_volume_date(int(row["closed_at_unix"]), tz_name) != volume_date:
            continue
        vol = conn.execute(
            "SELECT COALESCE(SUM(volume_ml), 0) AS total FROM dose_events WHERE batch_id = ?",
            (row["batch_id"],),
        ).fetchone()["total"]
        total += int(vol)
    return total


def js_json_dumps(obj: object) -> str:
    """Verifier fixture encoding: compact JSON with whole-number floats as integers."""
    if isinstance(obj, dict):
        parts = [f"{json.dumps(k)}:{js_json_dumps(v)}" for k, v in obj.items()]
        return "{" + ",".join(parts) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(js_json_dumps(item) for item in obj) + "]"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if obj is None:
        return "null"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        if math.isfinite(obj) and obj == int(obj):
            return str(int(obj))
        return format(obj, ".15g")
    return json.dumps(obj)


def compliance_hash(payload: dict) -> str:
    raw = js_json_dumps(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def expected_compliance(db_path: Path, profile_path: Path) -> dict:
    profile = load_profile(profile_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        batches_rows = conn.execute(
            """
            SELECT batch_id, zone_id, opened_at_unix, closed_at_unix
            FROM fertigation_batches
            WHERE status = 'CLOSED' ORDER BY batch_id ASC
            """
        ).fetchall()
        batches = []
        released = 0
        tz_name = profile["greenhouse_timezone"]
        target_ec = float(profile["target_ec_mS"])
        ph_min = float(profile["ph_min"])
        ph_max = float(profile["ph_max"])
        max_batch_vol = int(profile["max_batch_volume_ml"])
        max_daily = int(profile["max_daily_volume_ml_per_zone"])
        max_integral = float(profile["max_ec_drift_integral"])
        min_doses = int(profile["min_dose_count"])

        for brow in batches_rows:
            batch_id = brow["batch_id"]
            zone_id = brow["zone_id"]
            opened_at = int(brow["opened_at_unix"])
            closed_at = int(brow["closed_at_unix"])
            doses = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ec_mS, ph, volume_ml, recorded_at_unix FROM dose_events
                    WHERE batch_id = ? ORDER BY recorded_at_unix ASC
                    """,
                    (batch_id,),
                ).fetchall()
            ]
            dose_count = len(doses)
            integral = ec_drift_integral(
                conn, doses, opened_at, zone_id, target_ec, tz_name
            )
            ec_pass = integral <= max_integral
            ph_pass = ph_ok(doses, ph_min, ph_max)
            vol_ml = batch_volume_ml(doses)
            vol_pass = vol_ml <= max_batch_vol
            vdate = local_volume_date(closed_at, tz_name)
            daily_total = closed_daily_volume_ml(conn, zone_id, vdate, tz_name)
            daily_pass = daily_total <= max_daily
            release_ok = (
                ec_pass
                and ph_pass
                and vol_pass
                and daily_pass
                and dose_count >= min_doses
            )
            if release_ok:
                released += 1
            batches.append(
                {
                    "batch_id": batch_id,
                    "zone_id": zone_id,
                    "dose_count": dose_count,
                    "ec_drift_integral": integral,
                    "ec_ok": ec_pass,
                    "ph_ok": ph_pass,
                    "volume_ok": vol_pass,
                    "daily_volume_ok": daily_pass,
                    "batch_release_ok": release_ok,
                }
            )
        summary = {
            "batch_count": len(batches),
            "released_count": released,
        }
        payload = {
            "greenhouse_id": profile["greenhouse_id"],
            "batches": batches,
            "summary": summary,
        }
        return {
            **payload,
            "compliance_hash": compliance_hash(payload),
        }
    finally:
        conn.close()


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def canonical_crc_payload(obj: dict) -> str:
    """Compact sorted JSON body for line_crc (matches Go canonicalBytes on the line)."""
    keys = sorted(k for k in obj if k != "line_crc")
    parts = [f"{json.dumps(k)}:{js_json_dumps(obj[k])}" for k in keys]
    return "{" + ",".join(parts) + "}"


def serialize_jsonl_line(obj: dict) -> str:
    """One JSONL line with lexicographically sorted keys (verifier fixture encoding)."""
    keys = sorted(obj.keys())
    parts = [f"{json.dumps(k)}:{js_json_dumps(obj[k])}" for k in keys]
    return "{" + ",".join(parts) + "}"


def line_crc_for(line: dict) -> str:
    payload = canonical_crc_payload(line)
    return f"{crc16_ccitt_false(payload.encode('utf-8')):04X}"


def attach_line_crc(line: dict) -> dict:
    body = {k: v for k, v in line.items() if k != "line_crc"}
    return {**body, "line_crc": line_crc_for(body)}
