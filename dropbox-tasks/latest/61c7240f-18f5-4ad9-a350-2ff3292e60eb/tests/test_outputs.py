import csv
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from json import JSONDecodeError
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APP = Path("/app")
OUTPUT = APP / "output"
REPORT = OUTPUT / "weather-evidence.json"
CACHE = OUTPUT / "noaa-stations.json"
QUEUE = OUTPUT / "review-queue.json"
ROLLUPS = OUTPUT / "station-day-rollups.json"
EXCLUDED = OUTPUT / "excluded-readings.json"
TRENDS = OUTPUT / "station-trend-alerts.json"
HEALTH = OUTPUT / "station-health-summary.json"
FIXTURES = APP / "metadata/noaa-station-fixtures"
ALIASES = APP / "metadata/station-aliases.csv"
SENSOR_HEALTH = APP / "metadata/sensor-health.csv"


def run_workflow() -> bytes:
    """Clear output files, run the report script, and return report bytes."""
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    subprocess.run(["/app/scripts/generate_weather_report.sh"], check=True, cwd=APP)
    assert REPORT.exists(), "weather evidence report was not created"
    assert CACHE.exists(), "NOAA metadata cache was not created"
    assert QUEUE.exists(), "review queue was not created"
    assert ROLLUPS.exists(), "station day rollups were not created"
    assert EXCLUDED.exists(), "excluded reading audit was not created"
    assert TRENDS.exists(), "station trend alerts were not created"
    assert HEALTH.exists(), "station health summary was not created"
    return REPORT.read_bytes()


def load_rows():
    with ALIASES.open(newline="") as handle:
        aliases = {row["raw_station_id"]: row["station_id"] for row in csv.DictReader(handle)}
    with (APP / "data/station-readings.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["raw_station_id"] = row["station_id"]
        row["station_id"] = aliases.get(row["station_id"], row["station_id"])
    return rows


def load_sensor_windows():
    with ALIASES.open(newline="") as handle:
        aliases = {row["raw_station_id"]: row["station_id"] for row in csv.DictReader(handle)}
    windows = defaultdict(list)
    with SENSOR_HEALTH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["status"] != "offline":
                continue
            station_id = aliases.get(row["station_id"], row["station_id"])
            windows[station_id].append((
                parse_instant(row["status_start"]),
                parse_instant(row["status_end"]),
            ))
    return windows


def round_one(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def round_tenth(value) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def parse_instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def observed_instant(row):
    return parse_instant(row["observed_at"]).isoformat()


def observed_local_date(row, metadata):
    zone_name = metadata["time_zone"] if metadata["metadata_status"] == "active" else "UTC"
    return parse_instant(row["observed_at"]).astimezone(ZoneInfo(zone_name)).date().isoformat()


def in_sensor_blackout(row, windows):
    observed = parse_instant(row["observed_at"])
    return any(start <= observed < end for start, end in windows.get(row["station_id"], []))


def deduplicated_rows(rows):
    windows = load_sensor_windows()
    kept = {}
    duplicate_count = 0
    duplicate_stations = set()
    excluded_by_station = {}
    blackout_by_station = {}
    usable_rows = []
    for row in rows:
        station_id = row["station_id"]
        if row["quality_flag"] == "maintenance_hold" or not row["temp_c"]:
            excluded_by_station[station_id] = excluded_by_station.get(station_id, 0) + 1
            continue
        if in_sensor_blackout(row, windows):
            excluded_by_station[station_id] = excluded_by_station.get(station_id, 0) + 1
            blackout_by_station[station_id] = blackout_by_station.get(station_id, 0) + 1
            continue
        usable_rows.append(row)

    for row in usable_rows:
        key = (row["station_id"], observed_instant(row))
        sequence = int(row["ingest_sequence"])
        if key in kept:
            duplicate_count += 1
            duplicate_stations.add(row["station_id"])
            if sequence > int(kept[key]["ingest_sequence"]):
                kept[key] = row
        else:
            kept[key] = row
    return list(kept.values()), duplicate_count, duplicate_stations, excluded_by_station, blackout_by_station


def duplicate_counts_by_station(rows):
    windows = load_sensor_windows()
    kept = {}
    duplicate_counts = defaultdict(int)
    for row in rows:
        if row["quality_flag"] == "maintenance_hold" or not row["temp_c"] or in_sensor_blackout(row, windows):
            continue
        key = (row["station_id"], observed_instant(row))
        sequence = int(row["ingest_sequence"])
        if key in kept:
            duplicate_counts[row["station_id"]] += 1
            if sequence > int(kept[key]["ingest_sequence"]):
                kept[key] = row
        else:
            kept[key] = row
    return duplicate_counts


def expected_excluded_readings(rows):
    windows = load_sensor_windows()
    excluded = []
    for row in rows:
        reason = None
        if row["quality_flag"] == "maintenance_hold":
            reason = "maintenance_hold"
        elif not row["temp_c"]:
            reason = "blank_temp"
        elif in_sensor_blackout(row, windows):
            reason = "sensor_blackout"
        if reason:
            excluded.append({
                "raw_station_id": row["raw_station_id"],
                "station_id": row["station_id"],
                "observed_at_utc": observed_instant(row),
                "ingest_sequence": int(row["ingest_sequence"]),
                "reason": reason,
            })
    return sorted(excluded, key=lambda item: (
        item["station_id"],
        item["observed_at_utc"],
        item["ingest_sequence"],
    ))


def expected_trend_alerts(rows):
    kept_rows, _, _, _, _ = deduplicated_rows(rows)
    rows_by_station = defaultdict(list)
    for row in kept_rows:
        rows_by_station[row["station_id"]].append(row)

    alerts = []
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
            alerts.append({
                "station_id": station_id,
                "from_observed_at_utc": start.isoformat(),
                "to_observed_at_utc": end.isoformat(),
                "from_temp_c": round_one(Decimal(before["temp_c"])),
                "to_temp_c": round_one(Decimal(after["temp_c"])),
                "temp_delta_c": round_one(delta),
                "elapsed_minutes": elapsed_minutes,
                "rate_c_per_hour": round_tenth(rate),
                "direction": "rise" if delta > 0 else "fall",
            })

    return sorted(alerts, key=lambda item: (
        item["station_id"],
        item["from_observed_at_utc"],
        item["to_observed_at_utc"],
    ))


def fixture_metadata(station_id):
    path = FIXTURES / f"{station_id}.json"
    if not path.exists():
        return {"metadata_status": "missing", "name": None, "time_zone": None}
    try:
        properties = json.loads(path.read_text())["properties"]
    except (JSONDecodeError, KeyError, TypeError):
        return {"metadata_status": "missing", "name": None, "time_zone": None}
    if (
        properties.get("stationIdentifier") != station_id
        or not properties.get("name")
        or not properties.get("timeZone")
    ):
        return {"metadata_status": "missing", "name": None, "time_zone": None}
    try:
        ZoneInfo(properties["timeZone"])
    except ZoneInfoNotFoundError:
        return {"metadata_status": "missing", "name": None, "time_zone": None}
    return {
        "metadata_status": "active",
        "name": properties["name"],
        "time_zone": properties["timeZone"],
    }


def expected_review_queue(rows):
    kept_rows, _, duplicate_stations, excluded_by_station, blackout_by_station = deduplicated_rows(rows)
    expected_queue = {}
    for station_id in sorted({row["station_id"] for row in kept_rows}):
        station_rows = [row for row in kept_rows if row["station_id"] == station_id]
        metadata = fixture_metadata(station_id)
        reasons = []
        if metadata["metadata_status"] == "missing":
            reasons.append("missing_metadata")
        if any(row["quality_flag"] != "ok" for row in station_rows):
            reasons.append("non_ok_quality_flag")
        if station_id in duplicate_stations:
            reasons.append("duplicate_ingest")
        if excluded_by_station.get(station_id, 0):
            reasons.append("excluded_reading")
        if blackout_by_station.get(station_id, 0):
            reasons.append("sensor_blackout")
        if reasons:
            expected_queue[station_id] = {"reasons": sorted(reasons)}
    return expected_queue


def expected_health_summary(rows):
    kept_rows, _, _, excluded_by_station, blackout_by_station = deduplicated_rows(rows)
    duplicate_counts = duplicate_counts_by_station(rows)
    with ALIASES.open(newline="") as handle:
        aliases = {row["raw_station_id"]: row["station_id"] for row in csv.DictReader(handle)}

    offline_window_count = defaultdict(int)
    offline_minutes = defaultdict(int)
    with SENSOR_HEALTH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["status"] != "offline":
                continue
            station_id = aliases.get(row["station_id"], row["station_id"])
            offline_window_count[station_id] += 1
            start = parse_instant(row["status_start"])
            end = parse_instant(row["status_end"])
            offline_minutes[station_id] += int((end - start).total_seconds() // 60)

    review_queue = expected_review_queue(rows)
    station_ids = sorted({row["station_id"] for row in kept_rows} | set(offline_window_count))
    return [
        {
            "station_id": station_id,
            "offline_window_count": offline_window_count.get(station_id, 0),
            "offline_minutes": offline_minutes.get(station_id, 0),
            "blackout_reading_count": blackout_by_station.get(station_id, 0),
            "excluded_reading_count": excluded_by_station.get(station_id, 0),
            "duplicate_reading_count": duplicate_counts.get(station_id, 0),
            "requires_review": station_id in review_queue,
        }
        for station_id in station_ids
    ]


def test_report_schema_and_fixture_metadata_cache():
    """Verify the report and station cache match the CSV and bundled station fixtures."""
    run_workflow()
    report = json.loads(REPORT.read_text())
    cache = json.loads(CACHE.read_text())
    queue = json.loads(QUEUE.read_text())
    rollups = json.loads(ROLLUPS.read_text())
    excluded = json.loads(EXCLUDED.read_text())
    trends = json.loads(TRENDS.read_text())
    health = json.loads(HEALTH.read_text())
    rows = load_rows()
    kept_rows, duplicate_count, duplicate_stations, excluded_by_station, blackout_by_station = deduplicated_rows(rows)
    station_ids = sorted({row["station_id"] for row in kept_rows})

    assert set(report) == {
        "readings_count",
        "station_count",
        "missing_station_count",
        "duplicate_reading_count",
        "excluded_reading_count",
        "sensor_blackout_count",
        "stations",
    }
    assert report["readings_count"] == len(rows)
    assert report["station_count"] == len(station_ids)
    assert report["duplicate_reading_count"] == duplicate_count
    assert report["excluded_reading_count"] == sum(excluded_by_station.values())
    assert report["sensor_blackout_count"] == sum(blackout_by_station.values())
    assert [station["station_id"] for station in report["stations"]] == station_ids
    assert "CHI-ORD" not in station_ids
    assert "SFO-BAY" not in station_ids
    assert "SEA-TAC" not in station_ids
    assert "PHX-SKY" not in station_ids
    assert list(cache) == station_ids
    assert list(rollups) == station_ids
    assert excluded == expected_excluded_readings(rows)
    assert trends == expected_trend_alerts(rows)
    assert health == expected_health_summary(rows)
    assert [item["station_id"] for item in trends] == ["KORD", "KPHX"]
    assert [item["station_id"] for item in health] == sorted(item["station_id"] for item in health)
    assert {item["direction"] for item in trends} == {"fall", "rise"}
    assert {item["reason"] for item in excluded} == {"blank_temp", "maintenance_hold", "sensor_blackout"}
    assert excluded == sorted(excluded, key=lambda item: (
        item["station_id"],
        item["observed_at_utc"],
        item["ingest_sequence"],
    ))

    by_station = {station["station_id"]: station for station in report["stations"]}
    expected_missing = 0
    expected_queue = expected_review_queue(rows)
    for station_id in station_ids:
        station_rows = [row for row in kept_rows if row["station_id"] == station_id]
        station = by_station[station_id]
        metadata = cache[station_id]
        expected_metadata = fixture_metadata(station_id)
        expected_missing += expected_metadata["metadata_status"] == "missing"
        reasons = expected_queue.get(station_id, {}).get("reasons", [])

        assert set(station) == {
            "station_id",
            "metadata_status",
            "name",
            "time_zone",
            "reading_count",
            "excluded_reading_count",
            "average_temp_c",
            "quality_flags",
            "requires_review",
        }
        assert station["metadata_status"] in {"active", "missing"}
        assert metadata == expected_metadata
        assert station["metadata_status"] == metadata["metadata_status"]
        assert station["name"] == metadata["name"]
        assert station["time_zone"] == metadata["time_zone"]
        assert isinstance(station["reading_count"], int)
        assert station["reading_count"] == len(station_rows)
        assert isinstance(station["excluded_reading_count"], int)
        assert station["excluded_reading_count"] == excluded_by_station.get(station_id, 0)
        expected_avg = sum(Decimal(row["temp_c"]) for row in station_rows) / len(station_rows)
        assert station["average_temp_c"] == round_one(expected_avg)
        assert station["quality_flags"] == sorted({row["quality_flag"] for row in station_rows})
        assert isinstance(station["requires_review"], bool)
        assert station["requires_review"] == bool(reasons)
    assert report["missing_station_count"] == expected_missing
    assert queue == {key: expected_queue[key] for key in sorted(expected_queue)}


def test_station_health_summary_combines_sensor_and_review_state():
    """Verify health summary combines sensor windows, exclusions, duplicates, and review state."""
    run_workflow()
    rows = load_rows()
    health = json.loads(HEALTH.read_text())
    assert health == expected_health_summary(rows)
    by_station = {row["station_id"]: row for row in health}
    assert by_station["KORD"] == {
        "station_id": "KORD",
        "offline_window_count": 1,
        "offline_minutes": 60,
        "blackout_reading_count": 1,
        "excluded_reading_count": 1,
        "duplicate_reading_count": 2,
        "requires_review": True,
    }
    assert by_station["KSFO"]["offline_window_count"] == 1
    assert by_station["KSFO"]["offline_minutes"] == 45
    assert by_station["KMIA"]["offline_window_count"] == 0


def expected_day_rollups(rows):
    """Build expected local-day summaries from deduplicated readings and fixture time zones."""
    kept_rows, _, _, _, _ = deduplicated_rows(rows)
    station_ids = sorted({row["station_id"] for row in kept_rows})
    expected = {}
    for station_id in station_ids:
        metadata = fixture_metadata(station_id)
        grouped = defaultdict(list)
        for row in kept_rows:
            if row["station_id"] == station_id:
                grouped[observed_local_date(row, metadata)].append(row)
        expected[station_id] = []
        for local_date in sorted(grouped):
            day_rows = grouped[local_date]
            temps = [Decimal(row["temp_c"]) for row in day_rows]
            expected[station_id].append({
                "local_date": local_date,
                "reading_count": len(day_rows),
                "min_temp_c": round_one(min(temps)),
                "max_temp_c": round_one(max(temps)),
                "average_temp_c": round_one(sum(temps) / len(temps)),
                "quality_flags": sorted({row["quality_flag"] for row in day_rows}),
            })
    return expected


def test_station_day_rollups_use_local_station_dates():
    """Verify day rollups use active station time zones and UTC for missing metadata."""
    run_workflow()
    rows = load_rows()
    rollups = json.loads(ROLLUPS.read_text())
    assert rollups == expected_day_rollups(rows)
    assert rollups["KORD"][0]["local_date"] == "2026-05-31"
    assert rollups["KORD"][0]["reading_count"] == 3
    assert rollups["KORD"][0]["min_temp_c"] == 17.0
    assert rollups["KORD"][0]["max_temp_c"] == 19.1
    assert rollups["KORD"][0]["average_temp_c"] == 18.3
    assert rollups["KORD"][1] == {
        "local_date": "2026-06-01",
        "reading_count": 1,
        "min_temp_c": 12.0,
        "max_temp_c": 12.0,
        "average_temp_c": 12.0,
        "quality_flags": ["ok"],
    }
    assert rollups["KBOS"][0]["local_date"] == "2026-05-31"
    assert rollups["KBOS"][0]["quality_flags"] == ["ok"]
    assert rollups["KLAS"][0]["local_date"] == "2026-06-01"
    assert rollups["KSFO"][0]["local_date"] == "2026-05-31"
    assert rollups["KSFO"][1]["local_date"] == "2026-06-01"
    assert rollups["KSEA"][0]["local_date"] == "2026-06-01"
    assert rollups["KSEA"][0]["reading_count"] == 2
    assert rollups["KMDW"][0]["local_date"] == "2026-06-01"
    assert isinstance(rollups["KPHX"], list)
    assert rollups["KPHX"][0]["local_date"] == "2026-06-01"
    assert rollups["KPHX"][0]["reading_count"] == 3
    assert rollups["KPHX"][0]["quality_flags"] == ["heat_advisory", "ok"]
    assert rollups["KMIA"][0]["local_date"] == "2026-06-01"


def test_missing_station_and_review_logic_are_reported():
    """Verify absent, incomplete, and mismatched fixtures are surfaced for review."""
    run_workflow()
    report = json.loads(REPORT.read_text())
    queue = json.loads(QUEUE.read_text())
    by_station = {station["station_id"]: station for station in report["stations"]}

    assert by_station["KORD"]["metadata_status"] == "active"
    assert by_station["KORD"]["reading_count"] == 4
    assert by_station["KORD"]["average_temp_c"] == 16.7
    assert by_station["KORD"]["quality_flags"] == ["calibration_check", "ok"]
    assert by_station["KORD"]["requires_review"] is True
    assert by_station["KBOS"]["metadata_status"] == "active"
    assert by_station["KBOS"]["name"] == fixture_metadata("KBOS")["name"]
    assert by_station["KBOS"]["quality_flags"] == ["ok"]
    assert by_station["KBOS"]["average_temp_c"] == 2.3
    assert by_station["KBOS"]["requires_review"] is True
    assert by_station["KLAS"]["metadata_status"] == "missing"
    assert by_station["KLAS"]["name"] is None
    assert by_station["KLAS"]["quality_flags"] == ["ok", "sensor_drift"]
    assert by_station["KLAS"]["average_temp_c"] == 31.3
    assert by_station["KLAS"]["requires_review"] is True
    assert by_station["KSFO"]["metadata_status"] == "active"
    assert by_station["KDEN"]["metadata_status"] == "active"
    assert by_station["KORD"]["name"] == fixture_metadata("KORD")["name"]
    assert by_station["KSFO"]["name"] == fixture_metadata("KSFO")["name"]
    assert by_station["KDEN"]["name"] == fixture_metadata("KDEN")["name"]
    assert by_station["KDEN"]["reading_count"] == 2
    assert by_station["KDEN"]["excluded_reading_count"] == 2
    assert by_station["KDEN"]["quality_flags"] == ["ok"]
    assert by_station["KDEN"]["average_temp_c"] == 5.2
    assert by_station["KDEN"]["requires_review"] is True
    assert by_station["KPHX"]["metadata_status"] == "active"
    assert by_station["KPHX"]["name"] == fixture_metadata("KPHX")["name"]
    assert by_station["KPHX"]["reading_count"] == 3
    assert by_station["KPHX"]["excluded_reading_count"] == 1
    assert by_station["KPHX"]["quality_flags"] == ["heat_advisory", "ok"]
    assert by_station["KPHX"]["average_temp_c"] == 37.2
    assert by_station["KPHX"]["requires_review"] is True
    assert by_station["KMIA"]["metadata_status"] == "missing"
    assert by_station["KMIA"]["name"] is None
    assert by_station["KMIA"]["quality_flags"] == ["ok"]
    assert by_station["KMIA"]["average_temp_c"] == 28.3
    assert by_station["KMIA"]["requires_review"] is True
    assert by_station["KSEA"]["metadata_status"] == "missing"
    assert by_station["KSEA"]["name"] is None
    assert by_station["KSEA"]["requires_review"] is True
    assert by_station["KMDW"]["metadata_status"] == "missing"
    assert by_station["KMDW"]["name"] is None
    assert by_station["KMDW"]["quality_flags"] == ["manual_review", "ok"]
    assert by_station["KMDW"]["average_temp_c"] == 19.3
    assert by_station["KMDW"]["requires_review"] is True
    assert by_station["ZZ99"]["metadata_status"] == "missing"
    assert by_station["ZZ99"]["name"] is None
    assert by_station["ZZ99"]["requires_review"] is True
    assert by_station["KSFO"]["requires_review"] is True
    assert by_station["KSFO"]["quality_flags"] == ["ok", "suspect_sensor"]
    assert by_station["KSFO"]["average_temp_c"] == 14.0
    assert report["missing_station_count"] == 5
    assert report["duplicate_reading_count"] == 5
    assert report["excluded_reading_count"] == 6
    assert report["sensor_blackout_count"] == 4
    assert queue == {
        "KBOS": {"reasons": ["duplicate_ingest"]},
        "KDEN": {"reasons": ["excluded_reading", "sensor_blackout"]},
        "KORD": {"reasons": ["duplicate_ingest", "excluded_reading", "non_ok_quality_flag", "sensor_blackout"]},
        "KLAS": {"reasons": ["missing_metadata", "non_ok_quality_flag"]},
        "KMIA": {"reasons": ["missing_metadata"]},
        "KMDW": {"reasons": ["duplicate_ingest", "missing_metadata", "non_ok_quality_flag"]},
        "KPHX": {"reasons": ["duplicate_ingest", "excluded_reading", "non_ok_quality_flag"]},
        "KSEA": {"reasons": ["missing_metadata"]},
        "KSFO": {"reasons": ["excluded_reading", "non_ok_quality_flag", "sensor_blackout"]},
        "ZZ99": {"reasons": ["missing_metadata", "non_ok_quality_flag"]},
    }


def test_report_is_deterministic_for_same_inputs():
    """Verify repeated runs produce byte-identical report, cache, queue, and rollup JSON."""
    first = run_workflow()
    first_cache = CACHE.read_bytes()
    first_queue = QUEUE.read_bytes()
    first_rollups = ROLLUPS.read_bytes()
    first_excluded = EXCLUDED.read_bytes()
    first_trends = TRENDS.read_bytes()
    first_health = HEALTH.read_bytes()
    second = run_workflow()
    second_cache = CACHE.read_bytes()
    second_queue = QUEUE.read_bytes()
    second_rollups = ROLLUPS.read_bytes()
    second_excluded = EXCLUDED.read_bytes()
    second_trends = TRENDS.read_bytes()
    second_health = HEALTH.read_bytes()
    assert first == second
    assert first_cache == second_cache
    assert first_queue == second_queue
    assert first_rollups == second_rollups
    assert first_excluded == second_excluded
    assert first_trends == second_trends
    assert first_health == second_health


def test_new_station_inputs_are_recomputed_from_sources():
    """Verify the workflow handles a new aliased station without hardcoded fixtures."""
    readings_path = APP / "data/station-readings.csv"
    fixture_path = FIXTURES / "KLGA.json"
    original_readings = readings_path.read_text()
    original_aliases = ALIASES.read_text()
    original_sensor_health = SENSOR_HEALTH.read_text()
    try:
        readings_path.write_text(
            original_readings
            + "NYC-LGA,2026-06-01T03:30:00Z,1,20.0,ok\n"
            + "KLGA,2026-06-01T03:30:00+00:00,4,20.4,ok\n"
            + "KLGA,2026-06-01T04:00:00Z,1,17.9,ok\n"
            + "KLGA,2026-06-01T04:15:00Z,1,,ok\n"
            + "NYC-LGA,2026-06-01T05:00:00Z,1,18.0,ok\n"
        )
        ALIASES.write_text(original_aliases + "NYC-LGA,KLGA\n")
        SENSOR_HEALTH.write_text(
            original_sensor_health
            + "NYC-LGA,2026-06-01T04:45:00Z,2026-06-01T05:15:00Z,offline\n"
        )
        fixture_path.write_text(json.dumps({
            "id": "https://api.weather.gov/stations/KLGA",
            "type": "Feature",
            "properties": {
                "stationIdentifier": "KLGA",
                "name": "LaGuardia Airport",
                "timeZone": "America/New_York",
            },
        }, indent=2) + "\n")

        run_workflow()
        rows = load_rows()
        report = json.loads(REPORT.read_text())
        cache = json.loads(CACHE.read_text())
        queue = json.loads(QUEUE.read_text())
        rollups = json.loads(ROLLUPS.read_text())
        excluded = json.loads(EXCLUDED.read_text())
        trends = json.loads(TRENDS.read_text())
        health = json.loads(HEALTH.read_text())

        by_station = {station["station_id"]: station for station in report["stations"]}
        assert by_station["KLGA"] == {
            "station_id": "KLGA",
            "metadata_status": "active",
            "name": "LaGuardia Airport",
            "time_zone": "America/New_York",
            "reading_count": 2,
            "excluded_reading_count": 2,
            "average_temp_c": 19.2,
            "quality_flags": ["ok"],
            "requires_review": True,
        }
        assert cache["KLGA"] == {
            "metadata_status": "active",
            "name": "LaGuardia Airport",
            "time_zone": "America/New_York",
        }
        assert queue["KLGA"] == {
            "reasons": ["duplicate_ingest", "excluded_reading", "sensor_blackout"]
        }
        assert rollups["KLGA"] == [
            {
                "local_date": "2026-05-31",
                "reading_count": 1,
                "min_temp_c": 20.4,
                "max_temp_c": 20.4,
                "average_temp_c": 20.4,
                "quality_flags": ["ok"],
            },
            {
                "local_date": "2026-06-01",
                "reading_count": 1,
                "min_temp_c": 17.9,
                "max_temp_c": 17.9,
                "average_temp_c": 17.9,
                "quality_flags": ["ok"],
            },
        ]
        assert [item for item in excluded if item["station_id"] == "KLGA"] == [
            {
                "raw_station_id": "KLGA",
                "station_id": "KLGA",
                "observed_at_utc": "2026-06-01T04:15:00+00:00",
                "ingest_sequence": 1,
                "reason": "blank_temp",
            },
            {
                "raw_station_id": "NYC-LGA",
                "station_id": "KLGA",
                "observed_at_utc": "2026-06-01T05:00:00+00:00",
                "ingest_sequence": 1,
                "reason": "sensor_blackout",
            },
        ]
        assert [item for item in trends if item["station_id"] == "KLGA"] == [
            {
                "station_id": "KLGA",
                "from_observed_at_utc": "2026-06-01T03:30:00+00:00",
                "to_observed_at_utc": "2026-06-01T04:00:00+00:00",
                "from_temp_c": 20.4,
                "to_temp_c": 17.9,
                "temp_delta_c": -2.5,
                "elapsed_minutes": 30,
                "rate_c_per_hour": -5.0,
                "direction": "fall",
            }
        ]
        assert next(item for item in health if item["station_id"] == "KLGA") == {
            "station_id": "KLGA",
            "offline_window_count": 1,
            "offline_minutes": 30,
            "blackout_reading_count": 1,
            "excluded_reading_count": 2,
            "duplicate_reading_count": 1,
            "requires_review": True,
        }
        assert report["station_count"] == len({row["station_id"] for row in deduplicated_rows(rows)[0]})
    finally:
        readings_path.write_text(original_readings)
        ALIASES.write_text(original_aliases)
        SENSOR_HEALTH.write_text(original_sensor_health)
        if fixture_path.exists():
            fixture_path.unlink()
