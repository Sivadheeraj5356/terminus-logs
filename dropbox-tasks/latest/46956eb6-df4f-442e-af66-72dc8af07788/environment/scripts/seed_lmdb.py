#!/usr/bin/env python3
"""Seed LMDB telemetry scenarios for the replayer task."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import lmdb

ROOT = Path("/app/data")
SCENARIOS = ROOT / "scenarios.json"


def be_u64(v: int) -> bytes:
    return struct.pack(">Q", v)


def be_u32(v: int) -> bytes:
    return struct.pack(">I", v)


def put_json(env: lmdb.Environment, dbi: int, key: bytes, obj: dict) -> None:
    val = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    with env.begin(write=True) as txn:
        txn.put(key, val, db=dbi)


def seed_lane_alpha(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    base_ts = 1_700_000_000_000_000_000
    sample_rows = [
        (1001, base_ts + 1, {"cpu_pct": 42, "rss_kb": 8192, "state": "running"}),
        (1001, base_ts + 2, {"cpu_pct": 88, "rss_kb": 9216, "state": "running"}),
        (1002, base_ts + 3, {"cpu_pct": 15, "rss_kb": 4096, "state": "idle"}),
        (1003, base_ts + 4, {"cpu_pct": 55, "rss_kb": 6144, "state": "running"}),
    ]
    for pid, ts, body in sample_rows:
        key = be_u64(pid) + be_u64(ts)
        put_json(env, samples, key, body)

    error_rows = [
        (base_ts + 50, 1, {"pid": 1001, "code": "EPIPE", "msg": "broken pipe"}),
        (base_ts + 55, 2, {"pid": 1002, "code": "OOM", "msg": "rss spike"}),
        (base_ts + 60, 3, {"pid": 1003, "code": "TIMEOUT", "msg": "watchdog"}),
        (base_ts + 70, 4, {"pid": 1004, "code": "IO", "msg": "disk stall"}),
    ]
    for ts, seq, body in error_rows:
        key = be_u64(ts) + be_u32(seq)
        put_json(env, errors, key, body)

    restart_rows = [
        (1001, {"generation": 2, "reason": "crash", "restart_ts": base_ts + 100}),
        (1002, {"generation": 3, "reason": "oom", "restart_ts": base_ts + 110}),
        (
            1003,
            {
                "generation": 1,
                "reason": "deploy",
                "restart_ts": base_ts + 60_000_000_200,
            },
        ),
    ]
    for pid, body in restart_rows:
        put_json(env, restarts, be_u64(pid), body)

    env.close()


def seed_lane_beta(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    base_ts = 1_710_000_000_000_000_000
    for i in range(14):
        pid = 2000 + (i % 4)
        key = be_u64(pid) + be_u64(base_ts + i)
        put_json(env, samples, key, {"cpu_pct": i, "rss_kb": 2048 + i, "state": "run"})

    error_rows = [
        (base_ts + 10, 1, {"pid": 2001, "code": "SIGSEGV", "msg": "segv"}),
        (base_ts + 20, 2, {"pid": 2002, "code": "HANG", "msg": "blocked"}),
        (base_ts + 30, 3, {"pid": 2003, "code": "NET", "msg": "reset"}),
        (base_ts + 40, 4, {"pid": 2001, "code": "RETRY", "msg": "again"}),
        (base_ts + 50, 5, {"pid": 2004, "code": "IDLE", "msg": "noop"}),
        (base_ts + 60, 6, {"pid": 2002, "code": "WARN", "msg": "slow"}),
        (base_ts + 70, 7, {"pid": 2005, "code": "MISC", "msg": "other"}),
    ]
    for ts, seq, body in error_rows:
        put_json(env, errors, be_u64(ts) + be_u32(seq), body)

    restart_rows = [
        (2001, {"generation": 4, "reason": "segv", "restart_ts": base_ts + 80}),
        (2002, {"generation": 2, "reason": "hang", "restart_ts": base_ts + 90}),
    ]
    for pid, body in restart_rows:
        put_json(env, restarts, be_u64(pid), body)

    env.close()


def seed_lane_gamma(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    base_ts = 1_720_000_000_000_000_000
    for i in range(6):
        pid = 3000 + i
        put_json(
            env,
            samples,
            be_u64(pid) + be_u64(base_ts + i),
            {"cpu_pct": 10 * i, "rss_kb": 1024, "state": "ok"},
        )

    error_rows = [
        (base_ts + 5, 1, {"pid": 3001, "code": "A", "msg": "a"}),
        (base_ts + 15, 2, {"pid": 3002, "code": "B", "msg": "b"}),
        (base_ts + 25, 3, {"pid": 3003, "code": "C", "msg": "c"}),
    ]
    for ts, seq, body in error_rows:
        put_json(env, errors, be_u64(ts) + be_u32(seq), body)

    restart_rows = [
        (3001, {"generation": 1, "reason": "a", "restart_ts": base_ts + 30}),
        (3002, {"generation": 2, "reason": "b", "restart_ts": base_ts + 40}),
        (3003, {"generation": 3, "reason": "c", "restart_ts": base_ts + 50}),
        (3004, {"generation": 1, "reason": "d", "restart_ts": base_ts + 60}),
    ]
    for pid, body in restart_rows:
        put_json(env, restarts, be_u64(pid), body)

    env.close()


def seed_lane_delta(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    base_ts = 1_730_000_000_000_000_000
    sample_rows = [
        (4001, base_ts + 1, {"cpu_pct": 12, "rss_kb": 2048, "state": "run"}),
        (4002, base_ts + 2, {"cpu_pct": 18, "rss_kb": 3072, "state": "run"}),
        (4003, base_ts + 3, {"cpu_pct": 9, "rss_kb": 1536, "state": "idle"}),
    ]
    for pid, ts, body in sample_rows:
        put_json(env, samples, be_u64(pid) + be_u64(ts), body)

    error_rows = [
        (
            base_ts + 25_000_000_000,
            1,
            {"pid": 4001, "code": "WARN", "msg": "near restart"},
        ),
        (
            base_ts + 10_000_000_000,
            2,
            {"pid": 4002, "code": "OLD", "msg": "outside 30s window"},
        ),
        (
            base_ts + 40_000_000_000,
            3,
            {"pid": 4003, "code": "MISC", "msg": "no restart"},
        ),
    ]
    for ts, seq, body in error_rows:
        put_json(env, errors, be_u64(ts) + be_u32(seq), body)

    restart_rows = [
        (
            4001,
            {
                "generation": 2,
                "reason": "recover",
                "restart_ts": base_ts + 50_000_000_000,
            },
        ),
        (
            4002,
            {
                "generation": 3,
                "reason": "recover",
                "restart_ts": base_ts + 50_000_000_000,
            },
        ),
    ]
    for pid, body in restart_rows:
        put_json(env, restarts, be_u64(pid), body)

    env.close()


def seed_lane_epsilon(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    base_ts = 1_740_000_000_000_000_000
    sample_rows = [
        (5001, base_ts + 1, {"cpu_pct": 22, "rss_kb": 2048, "state": "run"}),
        (5003, base_ts + 2, {"cpu_pct": 31, "rss_kb": 3072, "state": "run"}),
    ]
    for pid, ts, body in sample_rows:
        put_json(env, samples, be_u64(pid) + be_u64(ts), body)

    error_rows = [
        (
            base_ts + 40_000_000_000,
            1,
            {"pid": 5001, "code": "WARN", "msg": "near restart"},
        ),
        (
            base_ts + 20_000_000_000,
            2,
            {"pid": 5002, "code": "OLD", "msg": "outside 45s window"},
        ),
        (base_ts + 35_000_000_000, 3, {"pid": 5003, "code": "A", "msg": "first hit"}),
        (base_ts + 44_000_000_000, 4, {"pid": 5003, "code": "B", "msg": "second hit"}),
    ]
    for ts, seq, body in error_rows:
        put_json(env, errors, be_u64(ts) + be_u32(seq), body)

    restart_rows = [
        (
            5001,
            {
                "generation": 2,
                "reason": "recover",
                "restart_ts": base_ts + 50_000_000_000,
            },
        ),
        (
            5002,
            {
                "generation": 3,
                "reason": "recover",
                "restart_ts": base_ts + 80_000_000_000,
            },
        ),
        (
            5003,
            {
                "generation": 4,
                "reason": "recover",
                "restart_ts": base_ts + 50_000_000_000,
            },
        ),
    ]
    for pid, body in restart_rows:
        put_json(env, restarts, be_u64(pid), body)

    env.close()


def seed_lane_zeta(path: Path) -> None:
    """Large boundary-timestamp lane exercising overflow-safe correlation and reporting."""
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=32 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    restart_ts = (1 << 64) - 10
    for i in range(900):
        pid = 6000 + i
        error_ts = restart_ts - 20
        put_json(
            env,
            samples,
            be_u64(pid) + be_u64(error_ts),
            {"cpu_pct": i % 100, "rss_kb": 4096 + i, "state": "boundary"},
        )
        put_json(
            env,
            errors,
            be_u64(error_ts) + be_u32(i + 1),
            {"pid": pid, "code": "BOUNDARY", "msg": "near u64 ceiling"},
        )
        put_json(
            env,
            restarts,
            be_u64(pid),
            {"generation": 1, "reason": "boundary", "restart_ts": restart_ts},
        )
    env.close()


def seed_lane_eta(path: Path) -> None:
    """Sparse odd-cardinality lane exposing conditional cursor cleanup."""
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")
    base_ts = 1_750_000_000_000_000_000
    put_json(
        env,
        errors,
        be_u64(base_ts + 10) + be_u32(1),
        {"pid": 7001, "code": "SPARSE", "msg": "single event"},
    )
    put_json(
        env,
        restarts,
        be_u64(7001),
        {"generation": 1, "reason": "sparse", "restart_ts": base_ts + 20},
    )
    env.close()


def seed_lane_iota(path: Path) -> None:
    """64-bit PID lane requiring lossless correlation and JSON serialization."""
    path.mkdir(parents=True, exist_ok=True)
    env = lmdb.open(str(path), map_size=8 << 20, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")
    base_ts = 1_760_000_000_000_000_000
    pids = [4_294_967_301, 8_589_934_599, 9_223_372_036_854_776_000]
    for i, pid in enumerate(pids):
        err_ts = base_ts + i * 100
        put_json(
            env,
            samples,
            be_u64(pid) + be_u64(err_ts),
            {"cpu_pct": 10 + i, "rss_kb": 8192 + i, "state": "wide-pid"},
        )
        put_json(
            env,
            errors,
            be_u64(err_ts) + be_u32(i + 1),
            {"pid": pid, "code": "WIDE", "msg": "64-bit pid"},
        )
        put_json(
            env,
            restarts,
            be_u64(pid),
            {"generation": i + 1, "reason": "wide-pid", "restart_ts": err_ts + 25},
        )
    env.close()


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    pack = {
        "schema_version": 1,
        "scenarios": [
            {"id": "lane_alpha", "db_path": "/app/data/lane_alpha", "loops": 24},
            {"id": "lane_beta", "db_path": "/app/data/lane_beta", "loops": 28},
            {"id": "lane_gamma", "db_path": "/app/data/lane_gamma", "loops": 16},
            {"id": "lane_delta", "db_path": "/app/data/lane_delta", "loops": 20},
            {"id": "lane_epsilon", "db_path": "/app/data/lane_epsilon", "loops": 22},
            {"id": "lane_zeta", "db_path": "/app/data/lane_zeta", "loops": 3},
            {"id": "lane_eta", "db_path": "/app/data/lane_eta", "loops": 40},
            {"id": "lane_iota", "db_path": "/app/data/lane_iota", "loops": 18},
        ],
    }
    seed_lane_alpha(Path(pack["scenarios"][0]["db_path"]))
    seed_lane_beta(Path(pack["scenarios"][1]["db_path"]))
    seed_lane_gamma(Path(pack["scenarios"][2]["db_path"]))
    seed_lane_delta(Path(pack["scenarios"][3]["db_path"]))
    seed_lane_epsilon(Path(pack["scenarios"][4]["db_path"]))
    seed_lane_zeta(Path(pack["scenarios"][5]["db_path"]))
    seed_lane_eta(Path(pack["scenarios"][6]["db_path"]))
    seed_lane_iota(Path(pack["scenarios"][7]["db_path"]))
    SCENARIOS.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
