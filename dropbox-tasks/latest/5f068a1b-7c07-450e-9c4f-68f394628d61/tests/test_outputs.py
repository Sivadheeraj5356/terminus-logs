"""Verifier for hardened orchard canopyledger replay pipeline."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
BIN = Path("/tmp/orchard-ledger")
FIX = APP / "fixtures"
ENV = APP / "environment"


def _fnv1a64(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _input_hash(parts: list[bytes]) -> str:
    blob = b"".join(parts)
    return f"{_fnv1a64(blob):016x}"


def _parse_settings(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"')
        if key == "base_temp_c":
            fields[key] = float(val)
        elif key == "bucket_anchor_epoch":
            fields[key] = int(val)
        else:
            fields[key] = val
    return fields


def _window_start(epoch: int, anchor: int) -> int:
    day = 86400
    return anchor + ((epoch - anchor) // day) * day


def _temp_celsius(unit: str, temp: float) -> float:
    if unit.upper() == "F":
        return (temp - 32.0) * 5.0 / 9.0
    return temp


def _round4(v: float) -> float:
    return round(v, 4)


def _parse_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    text = path.read_text()
    manifest_bytes = text.encode()
    allowed = {
        "manifest_version",
        "orchard_id",
        "profile",
        "sensor_registry",
        "readings",
        "corrections",
        "state_policy",
    }
    seen: dict[str, int] = {}
    m: dict[str, Any] = {"_dir": path.parent}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("readings"):
            inner = line[line.index("[") + 1 : -1]
            m["readings"] = [p.strip().strip('"') for p in inner.split(",") if p.strip()]
            seen["readings"] = seen.get("readings", 0) + 1
            continue
        if line.startswith("corrections"):
            inner = line[line.index("[") + 1 : -1]
            m["corrections"] = [p.strip().strip('"') for p in inner.split(",") if p.strip()]
            seen["corrections"] = seen.get("corrections", 0) + 1
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key not in allowed:
            raise ValueError(f"unknown manifest key: {key}")
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            raise ValueError(f"duplicate manifest key: {key}")
        m[key] = val.strip().strip('"')
    if m.get("manifest_version") != "2":
        raise ValueError("missing or bad manifest_version")
    for req in ("profile", "sensor_registry", "readings"):
        if req not in m:
            raise ValueError(f"missing required manifest field: {req}")
    if not m.get("readings"):
        raise ValueError("readings requires at least one file")
    if "corrections" not in m:
        m["corrections"] = []
    return m, manifest_bytes


def _resolve_manifest_path(mdir: Path, rel: str) -> Path:
    if Path(rel).is_absolute():
        raise ValueError(f"absolute paths not allowed: {rel}")
    clean = Path(rel)
    if ".." in clean.parts:
        raise ValueError(f"path escapes manifest directory: {rel}")
    resolved = (mdir / clean).resolve()
    fixture_root = (ENV / "fixtures").resolve()
    if not (str(resolved).startswith(str(mdir.resolve())) or str(resolved).startswith(str(fixture_root))):
        raise ValueError(f"path outside allowed roots: {rel}")
    return resolved


def _load_registry(path: Path) -> dict[str, dict[str, Any]]:
    reg: dict[str, dict[str, Any]] = {}
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sid = row["sensor_id"].strip()
            if not sid:
                raise ValueError("empty sensor_id")
            if sid in reg:
                raise ValueError(f"duplicate sensor_id: {sid}")
            unit = row["unit"].strip()
            if unit and unit not in ("C", "F"):
                raise ValueError(f"invalid unit: {unit}")
            entry: dict[str, Any] = {
                "unit": unit,
                "offset_c": float(row["offset_c"]),
                "active_from": int(row["active_from"]) if row["active_from"].strip() else None,
                "active_until": int(row["active_until"]) if row["active_until"].strip() else None,
            }
            reg[sid] = entry
    return reg


def _registry_active(reg: dict[str, dict[str, Any]], sensor: str, epoch: int) -> bool:
    if sensor not in reg:
        return False
    e = reg[sensor]
    if e["active_from"] is not None and epoch < e["active_from"]:
        return False
    if e["active_until"] is not None and epoch >= e["active_until"]:
        return False
    return True


def _load_feed(path: Path, feed_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row_num, row in enumerate(reader, start=1):
            rec = {
                "epoch_sec": int(row["epoch_sec"]),
                "sensor_id": row["sensor_id"].strip(),
                "temp": float(row["temp"]),
                "quality": row["quality"].strip(),
            }
            if row.get("reading_id", "").strip():
                rec["reading_id"] = row["reading_id"].strip()
                rec["rev"] = int(row["rev"])
            else:
                rec["reading_id"] = f"{feed_index}:{row_num}"
                rec["rev"] = 1
            rows.append(rec)
    return rows


def _load_corrections(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            op = row["op"].strip()
            if op not in ("upsert", "delete"):
                raise ValueError("invalid op")
            rec: dict[str, Any] = {
                "op": op,
                "reading_id": row["reading_id"].strip(),
                "rev": int(row["rev"]),
            }
            if op == "delete":
                if row["epoch_sec"].strip():
                    rec["epoch_sec"] = int(row["epoch_sec"])
                    rec["sensor_id"] = row["sensor_id"].strip()
                out.append(rec)
                continue
            rec.update(
                {
                    "epoch_sec": int(row["epoch_sec"]),
                    "sensor_id": row["sensor_id"].strip(),
                    "temp": float(row["temp"]),
                    "quality": row["quality"].strip(),
                }
            )
            out.append(rec)
    return out


def _collapse(
    feeds: list[list[dict[str, Any]]], corr_paths: list[Path]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    rev_seen: dict[str, set[int]] = {}
    origin: dict[str, dict[str, Any]] = {}

    def add(rec: dict[str, Any]) -> None:
        rid = rec["reading_id"]
        rev = rec["rev"]
        rev_seen.setdefault(rid, set())
        if rev in rev_seen[rid]:
            raise ValueError(f"duplicate revision: {rid} rev {rev}")
        rev_seen[rid].add(rev)
        if rid not in by_id or rev > by_id[rid]["rev"]:
            by_id[rid] = rec

    for feed in feeds:
        for r in feed:
            origin[r["reading_id"]] = r
            add({**r, "delete": False})
    for path in corr_paths:
        for rec in _load_corrections(path):
            if rec["op"] == "delete":
                add({"reading_id": rec["reading_id"], "rev": rec["rev"], "delete": True, **rec})
            else:
                add({**rec, "delete": False})
    return list(by_id.values()), origin


def _split_interval(start: int, end: int, anchor: int) -> list[tuple[int, float]]:
    if end <= start:
        return []
    day = 86400
    out: list[tuple[int, float]] = []
    pos = start
    while pos < end:
        b = _window_start(pos, anchor)
        bend = b + day
        seg_end = min(end, bend)
        out.append((b, (seg_end - pos) / 3600.0))
        pos = seg_end
    return out


def _reference_replay(manifest_path: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    m, manifest_bytes = _parse_manifest(manifest_path)
    mdir = manifest_path.parent
    profile = _resolve_manifest_path(mdir, m["profile"])
    registry_path = _resolve_manifest_path(mdir, m["sensor_registry"])
    site = _parse_settings(profile.read_text())
    reg = _load_registry(registry_path)

    hash_parts = [manifest_bytes]
    hash_parts.append(profile.read_bytes())
    hash_parts.append(registry_path.read_bytes())
    reading_paths = [_resolve_manifest_path(mdir, r) for r in m["readings"]]
    for p in reading_paths:
        hash_parts.append(p.read_bytes())
    corr_paths = [_resolve_manifest_path(mdir, c) for c in m["corrections"]]
    for p in corr_paths:
        hash_parts.append(p.read_bytes())
    input_hash = _input_hash(hash_parts)

    env_map = os.environ.copy()
    if env:
        env_map.update(env)
    base = float(env_map["ORCHARD_BASE_C"]) if env_map.get("ORCHARD_BASE_C") else float(site["base_temp_c"])
    env_unit = env_map.get("ORCHARD_INGEST_UNIT", site.get("ingest_unit", "C")).upper()
    anchor = int(site["bucket_anchor_epoch"])
    orchard_id = m.get("orchard_id", site["orchard_id"])

    feeds = [_load_feed(p, i) for i, p in enumerate(reading_paths)]
    raw_rows = [r for feed in feeds for r in feed]
    winners, origin = _collapse(feeds, corr_paths)

    raw_counts: dict[tuple[str, int], int] = {}
    for r in raw_rows:
        if not _registry_active(reg, r["sensor_id"], r["epoch_sec"]):
            continue
        b = _window_start(r["epoch_sec"], anchor)
        raw_counts[(r["sensor_id"], b)] = raw_counts.get((r["sensor_id"], b), 0) + 1

    accepted: list[dict[str, Any]] = []
    tomb_counts: dict[tuple[str, int], int] = {}
    for w in winners:
        if w.get("delete"):
            epoch = w.get("epoch_sec")
            sensor = w.get("sensor_id")
            if not epoch:
                o = origin[w["reading_id"]]
                epoch = o["epoch_sec"]
                sensor = o["sensor_id"]
            b = _window_start(epoch, anchor)
            tomb_counts[(sensor, b)] = tomb_counts.get((sensor, b), 0) + 1
            continue
        if not _registry_active(reg, w["sensor_id"], w["epoch_sec"]):
            continue
        if w["quality"] != "OK":
            continue
        unit = reg[w["sensor_id"]]["unit"] or env_unit
        temp_c = _temp_celsius(unit, w["temp"]) + reg[w["sensor_id"]]["offset_c"]
        accepted.append({"epoch_sec": w["epoch_sec"], "sensor_id": w["sensor_id"], "temp_c": temp_c})

    accepted.sort(key=lambda r: (r["epoch_sec"], r["sensor_id"]))
    ledger_acc: dict[tuple[str, int], dict[str, Any]] = {}
    accepted_counts: dict[tuple[str, int], int] = {}
    split_counts: dict[tuple[str, int], int] = {}
    prev_epoch: dict[str, int] = {}

    for r in accepted:
        b_reading = _window_start(r["epoch_sec"], anchor)
        prev = prev_epoch.get(r["sensor_id"], 0)
        interval_start = b_reading
        if prev > 0:
            interval_start = prev
        for b, hours in _split_interval(interval_start, r["epoch_sec"], anchor):
            k = (r["sensor_id"], b)
            if k not in ledger_acc:
                ledger_acc[k] = {
                    "orchard_id": orchard_id,
                    "sensor_id": r["sensor_id"],
                    "bucket_epoch": b,
                    "credit_hours": 0.0,
                    "sample_count": 0,
                }
            credit = hours if 0.0 <= r["temp_c"] < base else 0.0
            ledger_acc[k]["credit_hours"] += credit
            split_counts[k] = split_counts.get(k, 0) + 1
        bk = (r["sensor_id"], b_reading)
        ledger_acc.setdefault(
            bk,
            {
                "orchard_id": orchard_id,
                "sensor_id": r["sensor_id"],
                "bucket_epoch": b_reading,
                "credit_hours": 0.0,
                "sample_count": 0,
            },
        )
        ledger_acc[bk]["sample_count"] += 1
        accepted_counts[bk] = accepted_counts.get(bk, 0) + 1
        prev_epoch[r["sensor_id"]] = r["epoch_sec"]

    ledger = []
    sensors: set[str] = set()
    buckets: set[int] = set()
    for (sensor, bucket), row in ledger_acc.items():
        row["credit_hours"] = _round4(row["credit_hours"])
        ledger.append(row)
        sensors.add(sensor)
        buckets.add(bucket)
    ledger.sort(key=lambda r: (r["bucket_epoch"], r["sensor_id"]))

    audit_keys = set(raw_counts) | set(accepted_counts) | set(tomb_counts) | set(split_counts)
    audit = []
    for sensor, bucket in sorted(audit_keys, key=lambda k: (k[1], k[0])):
        audit.append(
            {
                "orchard_id": orchard_id,
                "sensor_id": sensor,
                "bucket_epoch": bucket,
                "raw_samples": raw_counts.get((sensor, bucket), 0),
                "accepted_samples": accepted_counts.get((sensor, bucket), 0),
                "tombstoned_samples": tomb_counts.get((sensor, bucket), 0),
                "split_segments": split_counts.get((sensor, bucket), 0),
                "input_hash": input_hash,
            }
        )

    state = {
        "state_version": 2,
        "input_hash": input_hash,
        "row_count": len(ledger),
        "sensor_count": len(sensors),
        "bucket_count": len(buckets),
    }
    return {"ledger": ledger, "audit": audit, "state": state, "input_hash": input_hash}


def _reference_simple(
    settings: dict[str, Any],
    readings: list[dict[str, Any]],
    *,
    env_base: str | None = None,
    env_unit: str | None = None,
) -> list[dict[str, Any]]:
    base = float(env_base) if env_base else float(settings["base_temp_c"])
    unit = env_unit.upper() if env_unit else str(settings.get("ingest_unit", "C")).upper()
    anchor = int(settings["bucket_anchor_epoch"])
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    prev_epoch: dict[str, int] = {}
    sorted_readings = sorted(readings, key=lambda r: (r["epoch_sec"], r["sensor_id"]))
    for row in sorted_readings:
        if row.get("quality", "OK") != "OK":
            continue
        sensor = row["sensor_id"]
        epoch = int(row["epoch_sec"])
        temp = float(row["temp"])
        temp_c = _temp_celsius(unit, temp)
        bstart = anchor + ((epoch - anchor) // 86400) * 86400 if epoch >= anchor else anchor
        prev = prev_epoch[sensor] if sensor in prev_epoch and prev_epoch[sensor] >= bstart else bstart
        interval_h = max(0.0, (epoch - prev) / 3600.0)
        credit = interval_h if 0.0 <= temp_c < base else 0.0
        key = (sensor, bstart)
        if key not in by_key:
            by_key[key] = {
                "sensor_id": sensor,
                "bucket_epoch": bstart,
                "credit_hours": 0.0,
                "sample_count": 0,
            }
        by_key[key]["credit_hours"] += credit
        by_key[key]["sample_count"] += 1
        prev_epoch[sensor] = epoch
    rows = list(by_key.values())
    for row in rows:
        row["credit_hours"] = _round4(row["credit_hours"])
    rows.sort(key=lambda r: (r["bucket_epoch"], r["sensor_id"]))
    return rows


def _load_readings(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                {
                    "epoch_sec": int(row["epoch_sec"]),
                    "sensor_id": row["sensor_id"],
                    "temp": float(row["temp"]),
                    "quality": row["quality"],
                }
            )
    return rows


@pytest.fixture(autouse=True)
def _rebuild() -> None:
    subprocess.run(
        ["go", "build", "-o", "/tmp/orchard-ledger", "/app/environment/cmd/orchardledger"],
        check=True,
        cwd="/app/environment",
    )


def _run_simple(profile: Path, sensors: Path, env: dict[str, str] | None = None) -> list[dict]:
    out = APP / "output"
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "s7_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    env_map = os.environ.copy()
    if env:
        env_map.update(env)
    subprocess.run(
        [str(BIN), "--profile", str(profile), "--sensors", str(sensors), "--out", str(out)],
        check=True,
        env=env_map,
    )
    rows = []
    for line in ledger.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _run_replay(
    manifest: Path,
    out: Path | None = None,
    state: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    out = out or (APP / "output")
    out.mkdir(parents=True, exist_ok=True)
    state = state or (out / "replay_state.json")
    env_map = os.environ.copy()
    if env:
        env_map.update(env)
    return subprocess.run(
        [str(BIN), "replay", "--manifest", str(manifest), "--out", str(out), "--state", str(state)],
        env=env_map,
        capture_output=True,
        text=True,
    )


def _read_ledger(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_audit(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        vals = line.split("\t")
        rows.append(
            {
                "orchard_id": vals[0],
                "sensor_id": vals[1],
                "bucket_epoch": int(vals[2]),
                "raw_samples": int(vals[3]),
                "accepted_samples": int(vals[4]),
                "tombstoned_samples": int(vals[5]),
                "split_segments": int(vals[6]),
                "input_hash": vals[7],
            }
        )
    return rows


def test_replay_default_fixture_matches_reference() -> None:
    """Default replay manifest must match independent reference ledger, audit, and state."""
    expected = _reference_replay(ENV / "fixtures" / "replay_manifest.toml")
    proc = _run_replay(ENV / "fixtures" / "replay_manifest.toml")
    assert proc.returncode == 0, proc.stderr
    out = APP / "output"
    got_ledger = _read_ledger(out / "s7_ledger.jsonl")
    got_audit = _read_audit(out / "s7_audit.tsv")
    got_state = json.loads((out / "replay_state.json").read_text())
    assert got_ledger == expected["ledger"]
    assert got_audit == expected["audit"]
    assert got_state == expected["state"]
    assert got_state["input_hash"] == expected["input_hash"]


def test_bucket_boundary_split_and_pre_anchor_flooring(tmp_path: Path) -> None:
    """Intervals crossing bucket boundaries and pre-anchor timestamps must split and floor correctly."""
    anchor = 1704067200
    root = tmp_path / "split_case"
    (root / "profiles").mkdir(parents=True)
    (root / "registries").mkdir()
    (root / "feeds").mkdir()
    (root / "profiles" / "base.toml").write_text(
        f'orchard_id = "split-test"\nbase_temp_c = 7.2\ningest_unit = "C"\nbucket_anchor_epoch = {anchor}\n'
    )
    (root / "registries" / "sensors.csv").write_text("sensor_id,unit,offset_c,active_from,active_until\nX1,C,0.0,,\n")
    (root / "feeds" / "day1.csv").write_text(
        "epoch_sec,sensor_id,temp,quality,reading_id,rev\n"
        f"{anchor - 3600},X1,5.0,OK,r-pre,1\n"
        f"{anchor + 82800},X1,5.0,OK,r-mid,1\n"
        f"{anchor + 90000},X1,5.0,OK,r-end,1\n"
    )
    manifest = root / "manifest.toml"
    manifest.write_text(
        'manifest_version = 2\norchard_id = "split-test"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["feeds/day1.csv"]\n'
        'corrections = []\n'
    )
    expected = _reference_replay(manifest)
    proc = _run_replay(manifest, out=tmp_path / "out")
    assert proc.returncode == 0, proc.stderr
    got = _read_ledger(tmp_path / "out" / "s7_ledger.jsonl")
    assert got == expected["ledger"]
    pre_bucket = _window_start(anchor - 3600, anchor)
    assert pre_bucket < anchor
    buckets = {r["bucket_epoch"] for r in got}
    assert pre_bucket in buckets
    assert anchor in buckets
    assert anchor + 86400 in buckets


def test_registry_unit_offset_and_env_precedence(tmp_path: Path) -> None:
    """Registry units, offsets, and ORCHARD env vars must apply in documented calibration order."""
    anchor = 1704067200
    root = tmp_path / "registry_case"
    for sub in ("profiles", "registries", "feeds"):
        (root / sub).mkdir(parents=True)
    (root / "profiles" / "base.toml").write_text(
        f'orchard_id = "reg-test"\nbase_temp_c = 7.2\ningest_unit = "C"\nbucket_anchor_epoch = {anchor}\n'
    )
    (root / "registries" / "sensors.csv").write_text(
        "sensor_id,unit,offset_c,active_from,active_until\n"
        "F1,F,0.0,,\n"
        "B1,,1.0,,\n"
    )
    (root / "feeds" / "day1.csv").write_text(
        "epoch_sec,sensor_id,temp,quality,reading_id,rev\n"
        f"{anchor + 3600},F1,41.0,OK,r-f,1\n"
        f"{anchor + 7200},B1,41.0,OK,r-b,1\n"
    )
    manifest = root / "manifest.toml"
    manifest.write_text(
        'manifest_version = 2\norchard_id = "reg-test"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["feeds/day1.csv"]\n'
        'corrections = []\n'
    )
    expected = _reference_replay(manifest, env={"ORCHARD_INGEST_UNIT": "F", "ORCHARD_BASE_C": "6.0"})
    proc = _run_replay(manifest, out=tmp_path / "out", env={"ORCHARD_INGEST_UNIT": "F", "ORCHARD_BASE_C": "6.0"})
    assert proc.returncode == 0, proc.stderr
    got = _read_ledger(tmp_path / "out" / "s7_ledger.jsonl")
    assert got == expected["ledger"]


def test_revision_collapse_tombstone_and_duplicate_rev_rejection(tmp_path: Path) -> None:
    """Revision collapse, tombstones, and duplicate revision rejection must behave as documented."""
    anchor = 1704067200
    root = tmp_path / "rev_case"
    for sub in ("profiles", "registries", "feeds", "corrections"):
        (root / sub).mkdir(parents=True)
    (root / "profiles" / "base.toml").write_text(
        f'orchard_id = "rev-test"\nbase_temp_c = 7.2\ningest_unit = "C"\nbucket_anchor_epoch = {anchor}\n'
    )
    (root / "registries" / "sensors.csv").write_text("sensor_id,unit,offset_c,active_from,active_until\nR1,C,0.0,,\n")
    (root / "feeds" / "day1.csv").write_text(
        "epoch_sec,sensor_id,temp,quality,reading_id,rev\n"
        f"{anchor + 3600},R1,5.0,OK,r1,1\n"
        f"{anchor + 7200},R1,5.0,OK,r2,1\n"
    )
    (root / "corrections" / "patch.csv").write_text(
        "op,reading_id,epoch_sec,sensor_id,temp,quality,rev\n"
        f"upsert,r1,{anchor + 3600},R1,5.0,OK,2\n"
        f"delete,r2,{anchor + 7200},R1,5.0,OK,2\n"
    )
    manifest = root / "manifest.toml"
    manifest.write_text(
        'manifest_version = 2\norchard_id = "rev-test"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["feeds/day1.csv"]\n'
        'corrections = ["corrections/patch.csv"]\n'
    )
    expected = _reference_replay(manifest)
    proc = _run_replay(manifest, out=tmp_path / "out_ok")
    assert proc.returncode == 0, proc.stderr
    got = _read_ledger(tmp_path / "out_ok" / "s7_ledger.jsonl")
    assert got == expected["ledger"]

    bad_root = tmp_path / "dup_case"
    shutil.copytree(root, bad_root)
    (bad_root / "corrections" / "dup.csv").write_text(
        "op,reading_id,epoch_sec,sensor_id,temp,quality,rev\n"
        f"upsert,r1,{anchor + 3600},R1,5.0,OK,2\n"
    )
    bad_manifest = bad_root / "manifest.toml"
    bad_manifest.write_text(
        'manifest_version = 2\norchard_id = "rev-test"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["feeds/day1.csv"]\n'
        'corrections = ["corrections/patch.csv", "corrections/dup.csv"]\n'
    )
    out_bad = tmp_path / "out_bad"
    out_bad.mkdir()
    (out_bad / "s7_ledger.jsonl").write_text('{"keep": true}\n')
    before = (out_bad / "s7_ledger.jsonl").read_bytes()
    proc = _run_replay(bad_manifest, out=out_bad)
    assert proc.returncode != 0
    assert (out_bad / "s7_ledger.jsonl").read_bytes() == before


def test_replay_state_idempotence_and_stale_state_ignored(tmp_path: Path) -> None:
    """Repeated replays must be idempotent and stale state must be ignored after input changes."""
    manifest = ENV / "fixtures" / "replay_manifest.toml"
    out = tmp_path / "state_out"
    proc1 = _run_replay(manifest, out=out)
    assert proc1.returncode == 0, proc1.stderr
    first_ledger = (out / "s7_ledger.jsonl").read_bytes()
    first_audit = (out / "s7_audit.tsv").read_bytes()
    first_state = (out / "replay_state.json").read_bytes()
    proc2 = _run_replay(manifest, out=out)
    assert proc2.returncode == 0, proc2.stderr
    assert (out / "s7_ledger.jsonl").read_bytes() == first_ledger
    assert (out / "s7_audit.tsv").read_bytes() == first_audit
    assert (out / "replay_state.json").read_bytes() == first_state

    changed_root = tmp_path / "changed_manifest"
    shutil.copytree(ENV / "fixtures", changed_root)
    feed = changed_root / "feeds" / "day2.csv"
    existing = feed.read_text()
    anchor_epoch = int(_parse_settings((changed_root / "profiles" / "base.toml").read_text())["bucket_anchor_epoch"])
    feed.write_text(existing + f"{anchor_epoch + 183280},A1,5.0,OK,r-extra,1\n")
    changed_manifest = changed_root / "replay_manifest.toml"
    proc3 = _run_replay(changed_manifest, out=out)
    assert proc3.returncode == 0, proc3.stderr
    assert (out / "s7_ledger.jsonl").read_bytes() != first_ledger
    lines = _read_ledger(out / "s7_ledger.jsonl")
    ids = [(r["bucket_epoch"], r["sensor_id"], r["sample_count"]) for r in lines]
    assert len(ids) == len(set(ids))


def test_atomic_failure_does_not_clobber_existing_outputs(tmp_path: Path) -> None:
    """Invalid replay runs must not overwrite prior valid output artifacts."""
    good_dir = tmp_path / "good_bundle"
    shutil.copytree(ENV / "fixtures", good_dir)
    good = good_dir / "replay_manifest.toml"
    out = tmp_path / "atomic_out"
    proc = _run_replay(good, out=out)
    assert proc.returncode == 0, proc.stderr
    saved = {
        "ledger": (out / "s7_ledger.jsonl").read_bytes(),
        "audit": (out / "s7_audit.tsv").read_bytes(),
        "state": (out / "replay_state.json").read_bytes(),
    }
    bad = tmp_path / "bad_manifest.toml"
    bad.write_text('manifest_version = 2\norchard_id = "x"\nunknown_key = true\n')
    proc_bad = _run_replay(bad, out=out)
    assert proc_bad.returncode != 0
    assert (out / "s7_ledger.jsonl").read_bytes() == saved["ledger"]
    assert (out / "s7_audit.tsv").read_bytes() == saved["audit"]
    assert (out / "replay_state.json").read_bytes() == saved["state"]


def test_manifest_path_safety_and_unknown_keys(tmp_path: Path) -> None:
    """Unknown manifest keys, missing fields, and unsafe paths must fail without partial outputs."""
    out = tmp_path / "manifest_out"
    out.mkdir()
    (out / "s7_ledger.jsonl").write_text("stub\n")

    unknown = tmp_path / "unknown.toml"
    unknown.write_text('manifest_version = 2\norchard_id = "x"\nfoo = "bar"\n')
    assert _run_replay(unknown, out=out).returncode != 0
    assert (out / "s7_ledger.jsonl").read_text() == "stub\n"

    missing = tmp_path / "missing.toml"
    missing.write_text('manifest_version = 2\norchard_id = "x"\n')
    assert _run_replay(missing, out=out).returncode != 0

    root = tmp_path / "escape"
    (root / "profiles").mkdir(parents=True)
    (root / "registries").mkdir()
    (root / "feeds").mkdir()
    (root / "profiles" / "base.toml").write_text(
        'orchard_id = "e"\nbase_temp_c = 7.2\ningest_unit = "C"\nbucket_anchor_epoch = 1704067200\n'
    )
    (root / "registries" / "sensors.csv").write_text("sensor_id,unit,offset_c,active_from,active_until\nE1,C,0.0,,\n")
    (root / "feeds" / "day1.csv").write_text(
        "epoch_sec,sensor_id,temp,quality,reading_id,rev\n1704067200,E1,5.0,OK,r1,1\n"
    )
    escape = root / "manifest.toml"
    escape.write_text(
        'manifest_version = 2\norchard_id = "e"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["../fixtures/feeds/day1.csv"]\n'
        'corrections = []\n'
    )
    assert _run_replay(escape, out=out).returncode != 0


def test_simple_mode_backward_compatibility() -> None:
    """Simple CLI mode must preserve Celsius, Fahrenheit, env precedence, and sorted output."""
    site = _parse_settings((FIX / "profile_primary.toml").read_text())
    readings = _load_readings(FIX / "sensors_primary.csv")
    expected = _reference_simple(site, readings)
    got = _run_simple(FIX / "profile_primary.toml", FIX / "sensors_primary.csv")
    assert got == expected

    site_f = _parse_settings((FIX / "profile_fahrenheit.toml").read_text())
    readings_f = _load_readings(FIX / "sensors_fahrenheit.csv")
    expected_f = _reference_simple(site_f, readings_f)
    got_f = _run_simple(FIX / "profile_fahrenheit.toml", FIX / "sensors_fahrenheit.csv")
    assert got_f == expected_f

    expected_env = _reference_simple(site_f, readings_f, env_base="6.0")
    got_env = _run_simple(
        FIX / "profile_fahrenheit.toml",
        FIX / "sensors_fahrenheit.csv",
        env={"ORCHARD_BASE_C": "6.0"},
    )
    assert got_env == expected_env

    keys = [(r["bucket_epoch"], r["sensor_id"]) for r in got]
    assert keys == sorted(keys)


def test_cli_usage_errors() -> None:
    """Missing required CLI flags must exit with code 2."""
    cases = [
        [str(BIN)],
        [str(BIN), "--profile", "x"],
        [str(BIN), "replay"],
        [str(BIN), "replay", "--manifest", "x"],
    ]
    for cmd in cases:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 2, cmd


class _DetRand:
    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (self._state * 6364136223846793005 + 1) & 0xFFFFFFFFFFFFFFFF
        return self._state

    def choice(self, options: list[str]) -> str:
        return options[self._next() % len(options)]

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (self._next() % 10_000) / 10_000.0 * (hi - lo)

    def randint(self, lo: int, hi: int) -> int:
        return lo + (self._next() % (hi - lo + 1))


def test_generated_seeded_replay_bundle(tmp_path: Path) -> None:
    """Deterministic generated replay bundle must match the Python reference model."""
    rng = _DetRand(20260708)
    anchor = 1704067200
    root = tmp_path / "generated"
    for sub in ("profiles", "registries", "feeds", "corrections"):
        (root / sub).mkdir(parents=True)
    (root / "profiles" / "base.toml").write_text(
        f'orchard_id = "gen"\nbase_temp_c = 7.2\ningest_unit = "C"\nbucket_anchor_epoch = {anchor}\n'
    )
    sensors = []
    feed_lines = ["epoch_sec,sensor_id,temp,quality,reading_id,rev"]
    corr_lines = ["op,reading_id,epoch_sec,sensor_id,temp,quality,rev"]
    for i in range(4):
        unit = rng.choice(["C", "F", ""])
        offset = round(rng.uniform(-1.0, 1.5), 2)
        sensors.append(f"S{i},{unit},{offset},,")
        for j in range(5):
            epoch = anchor + rng.randint(-7200, 200000)
            temp = round(rng.uniform(35.0, 50.0), 1)
            feed_lines.append(f"{epoch},S{i},{temp},OK,g{i}-{j},1")
    (root / "registries" / "sensors.csv").write_text(
        "sensor_id,unit,offset_c,active_from,active_until\n" + "\n".join(sensors) + "\n"
    )
    (root / "feeds" / "day1.csv").write_text("\n".join(feed_lines) + "\n")
    (root / "corrections" / "patch.csv").write_text(
        corr_lines[0] + "\n" + f"upsert,g0-0,{anchor + 1000},S0,40.0,OK,2\n"
    )
    manifest = root / "manifest.toml"
    manifest.write_text(
        'manifest_version = 2\norchard_id = "gen"\n'
        'profile = "profiles/base.toml"\n'
        'sensor_registry = "registries/sensors.csv"\n'
        'readings = ["feeds/day1.csv"]\n'
        'corrections = ["corrections/patch.csv"]\n'
    )
    expected = _reference_replay(manifest)
    proc = _run_replay(manifest, out=tmp_path / "gen_out")
    assert proc.returncode == 0, proc.stderr
    got = _read_ledger(tmp_path / "gen_out" / "s7_ledger.jsonl")
    assert got == expected["ledger"]
