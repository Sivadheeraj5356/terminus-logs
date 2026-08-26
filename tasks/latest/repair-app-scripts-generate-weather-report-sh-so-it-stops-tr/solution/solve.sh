#!/usr/bin/env bash
set -euo pipefail

cat > /app/scripts/generate_weather_report.sh <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/output

python3 - <<'PY'
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

data_path = Path("/app/data/station-readings.csv")
alias_path = Path("/app/metadata/station-aliases.csv")
sensor_path = Path("/app/metadata/sensor-health.csv")
fixture_dir = Path("/app/metadata/noaa-station-fixtures")
output_dir = Path("/app/output")
report_path = output_dir / "weather-evidence.json"
cache_path = output_dir / "noaa-stations.json"
queue_path = output_dir / "review-queue.json"
rollup_path = output_dir / "station-day-rollups.json"
excluded_path = output_dir / "excluded-readings.json"
trend_path = output_dir / "station-trend-alerts.json"
health_path = output_dir / "station-health-summary.json"

with data_path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
with alias_path.open(newline="", encoding="utf-8") as handle:
    aliases = {row["raw_station_id"].strip(): row["station_id"].strip() for row in csv.DictReader(handle)}
for row in rows:
    row["raw_station_id"] = row["station_id"].strip()
    row["station_id"] = aliases.get(row["raw_station_id"], row["raw_station_id"])

def observed_instant(row):
    observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
    return observed.astimezone(timezone.utc).isoformat()

def parse_instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

sensor_windows = defaultdict(list)
offline_window_count = defaultdict(int)
offline_minutes = defaultdict(int)
with sensor_path.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        if row["status"].strip() != "offline":
            continue
        station_id = aliases.get(row["station_id"].strip(), row["station_id"].strip())
        start = parse_instant(row["status_start"])
        end = parse_instant(row["status_end"])
        sensor_windows[station_id].append((start, end))
        offline_window_count[station_id] += 1
        offline_minutes[station_id] += int((end - start).total_seconds() // 60)

def in_sensor_blackout(row):
    observed = parse_instant(row["observed_at"])
    return any(start <= observed < end for start, end in sensor_windows.get(row["station_id"].strip(), []))

excluded_by_station = defaultdict(int)
blackout_by_station = defaultdict(int)
usable_rows = []
excluded_rows = []
for row in rows:
    station_id = row["station_id"].strip()
    reason = None
    if row["quality_flag"].strip() == "maintenance_hold":
        reason = "maintenance_hold"
    elif not row["temp_c"].strip():
        reason = "blank_temp"
    elif in_sensor_blackout(row):
        reason = "sensor_blackout"

    if reason:
        excluded_by_station[station_id] += 1
        if reason == "sensor_blackout":
            blackout_by_station[station_id] += 1
        excluded_rows.append({
            "raw_station_id": row["raw_station_id"],
            "station_id": station_id,
            "observed_at_utc": observed_instant(row),
            "ingest_sequence": int(row["ingest_sequence"]),
            "reason": reason,
        })
    else:
        usable_rows.append(row)

kept = {}
duplicate_count = 0
duplicate_counts_by_station = defaultdict(int)
duplicate_stations = set()
for row in usable_rows:
    key = (row["station_id"].strip(), observed_instant(row))
    sequence = int(row["ingest_sequence"])
    if key in kept:
        duplicate_count += 1
        duplicate_counts_by_station[key[0]] += 1
        duplicate_stations.add(key[0])
        if sequence > int(kept[key]["ingest_sequence"]):
            kept[key] = row
    else:
        kept[key] = row

kept_rows = list(kept.values())
station_ids = sorted({row["station_id"].strip() for row in kept_rows})

def metadata_for(station_id):
    path = fixture_dir / f"{station_id}.json"
    if path.exists():
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
            props = fixture.get("properties") or {}
            if (
                props.get("stationIdentifier") == station_id
                and props.get("name")
                and props.get("timeZone")
            ):
                ZoneInfo(props["timeZone"])
                return {
                    "metadata_status": "active",
                    "name": props["name"],
                    "time_zone": props["timeZone"],
                }
        except (OSError, json.JSONDecodeError, ZoneInfoNotFoundError):
            pass
    return {"metadata_status": "missing", "name": None, "time_zone": None}

def round_one(values):
    total = sum(Decimal(row["temp_c"]) for row in values)
    return float((total / len(values)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

def round_decimal(value):
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

def local_date_for(row, metadata):
    zone_name = metadata["time_zone"] if metadata["metadata_status"] == "active" else "UTC"
    observed = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
    return observed.astimezone(ZoneInfo(zone_name)).date().isoformat()

rows_by_station = defaultdict(list)
for row in kept_rows:
    rows_by_station[row["station_id"].strip()].append(row)

trend_alerts = []
for station_id in sorted(rows_by_station):
    ordered = sorted(
        rows_by_station[station_id],
        key=lambda row: (parse_instant(row["observed_at"]), int(row["ingest_sequence"])),
    )
    for before, after in zip(ordered, ordered[1:]):
        start = parse_instant(before["observed_at"])
        end = parse_instant(after["observed_at"])
        elapsed_minutes = int((end - start).total_seconds() // 60)
        if elapsed_minutes <= 0:
            continue
        delta = Decimal(after["temp_c"]) - Decimal(before["temp_c"])
        rate = delta / (Decimal(elapsed_minutes) / Decimal(60))
        if abs(delta) < Decimal("2.0") or abs(rate) < Decimal("4.0"):
            continue
        trend_alerts.append({
            "station_id": station_id,
            "from_observed_at_utc": start.isoformat(),
            "to_observed_at_utc": end.isoformat(),
            "from_temp_c": round_decimal(Decimal(before["temp_c"])),
            "to_temp_c": round_decimal(Decimal(after["temp_c"])),
            "temp_delta_c": round_decimal(delta),
            "elapsed_minutes": elapsed_minutes,
            "rate_c_per_hour": round_decimal(rate),
            "direction": "rise" if delta > 0 else "fall",
        })
trend_alerts.sort(key=lambda item: (
    item["station_id"],
    item["from_observed_at_utc"],
    item["to_observed_at_utc"],
))

cache = {}
queue = {}
stations = []
rollups = {}
missing_count = 0
for station_id in station_ids:
    metadata = metadata_for(station_id)
    cache[station_id] = metadata
    if metadata["metadata_status"] == "missing":
        missing_count += 1

    station_rows = rows_by_station[station_id]
    flags = sorted({row["quality_flag"].strip() for row in station_rows})
    reasons = []
    if metadata["metadata_status"] == "missing":
        reasons.append("missing_metadata")
    if any(flag != "ok" for flag in flags):
        reasons.append("non_ok_quality_flag")
    if station_id in duplicate_stations:
        reasons.append("duplicate_ingest")
    if excluded_by_station[station_id]:
        reasons.append("excluded_reading")
    if blackout_by_station[station_id]:
        reasons.append("sensor_blackout")

    stations.append({
        "station_id": station_id,
        "metadata_status": metadata["metadata_status"],
        "name": metadata["name"],
        "time_zone": metadata["time_zone"],
        "reading_count": len(station_rows),
        "excluded_reading_count": excluded_by_station[station_id],
        "average_temp_c": round_one(station_rows),
        "quality_flags": flags,
        "requires_review": bool(reasons),
    })
    if reasons:
        queue[station_id] = {"reasons": sorted(reasons)}

    grouped = defaultdict(list)
    for row in station_rows:
        grouped[local_date_for(row, metadata)].append(row)
    rollups[station_id] = []
    for local_date in sorted(grouped):
        day_rows = grouped[local_date]
        temps = [Decimal(row["temp_c"]) for row in day_rows]
        rollups[station_id].append({
            "local_date": local_date,
            "reading_count": len(day_rows),
            "min_temp_c": round_decimal(min(temps)),
            "max_temp_c": round_decimal(max(temps)),
            "average_temp_c": round_decimal(sum(temps) / len(temps)),
            "quality_flags": sorted({row["quality_flag"].strip() for row in day_rows}),
        })

report = {
    "readings_count": len(rows),
    "station_count": len(station_ids),
    "missing_station_count": missing_count,
    "duplicate_reading_count": duplicate_count,
    "excluded_reading_count": sum(excluded_by_station.values()),
    "sensor_blackout_count": sum(blackout_by_station.values()),
    "stations": stations,
}

health_summary = []
health_station_ids = sorted(set(station_ids) | set(offline_window_count))
for station_id in health_station_ids:
    health_summary.append({
        "station_id": station_id,
        "offline_window_count": offline_window_count[station_id],
        "offline_minutes": offline_minutes[station_id],
        "blackout_reading_count": blackout_by_station[station_id],
        "excluded_reading_count": excluded_by_station[station_id],
        "duplicate_reading_count": duplicate_counts_by_station[station_id],
        "requires_review": station_id in queue,
    })

output_dir.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
rollup_path.write_text(json.dumps(rollups, indent=2, sort_keys=True) + "\n", encoding="utf-8")
excluded_rows.sort(key=lambda item: (item["station_id"], item["observed_at_utc"], item["ingest_sequence"]))
excluded_path.write_text(json.dumps(excluded_rows, indent=2) + "\n", encoding="utf-8")
trend_path.write_text(json.dumps(trend_alerts, indent=2) + "\n", encoding="utf-8")
health_path.write_text(json.dumps(health_summary, indent=2) + "\n", encoding="utf-8")
PY
SCRIPT

chmod +x /app/scripts/generate_weather_report.sh
/app/scripts/generate_weather_report.sh
jq . /app/output/weather-evidence.json
jq . /app/output/review-queue.json
jq . /app/output/station-day-rollups.json
jq . /app/output/excluded-readings.json
jq . /app/output/station-trend-alerts.json
jq . /app/output/station-health-summary.json
