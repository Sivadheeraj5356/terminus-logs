"""Independent expected-value engine for LMDB telemetry scenarios."""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import lmdb

DATA = Path("/app/data")
PACK = DATA / "scenarios.json"
CONFIG = Path("/app/config/replayer.toml")


def _be_u64(raw: bytes) -> int:
    return struct.unpack(">Q", raw)[0]


def _load_pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def _load_config_windows() -> tuple[int, dict[str, int]]:
    default = 60_000_000_000
    overrides: dict[str, int] = {}
    section = ""
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            section = m.group(1)
            continue
        if "=" not in line:
            continue
        key, val = [part.strip() for part in line.split("=", 1)]
        if key == "correlation_window_ns_default":
            default = int(val)
        elif key == "correlation_window_ns" and section.startswith("scenarios."):
            sid = section.split(".", 1)[1]
            overrides[sid] = int(val)
    return default, overrides


def window_for_scenario(scenario_id: str) -> int:
    default, overrides = _load_config_windows()
    return overrides.get(scenario_id, default)


def _scan_counts(db_path: Path, window_ns: int) -> dict:
    env = lmdb.open(str(db_path), readonly=True, lock=False, max_dbs=4)
    samples = env.open_db(b"samples")
    errors = env.open_db(b"errors")
    restarts = env.open_db(b"restarts")

    with env.begin() as txn:
        samples_scanned = sum(1 for _ in txn.cursor(db=samples))
        errors_seen = sum(1 for _ in txn.cursor(db=errors))
        restarts_seen = sum(1 for _ in txn.cursor(db=restarts))

        restart_rows: list[tuple[int, int]] = []
        for key, val in txn.cursor(db=restarts):
            pid = _be_u64(key)
            payload = json.loads(val.decode("utf-8"))
            restart_rows.append((pid, int(payload["restart_ts"])))

        error_rows: list[tuple[int, int]] = []
        for key, val in txn.cursor(db=errors):
            ts = _be_u64(key[:8])
            payload = json.loads(val.decode("utf-8"))
            error_rows.append((int(payload["pid"]), ts))

    env.close()

    affected: set[int] = set()
    triples = 0
    for pid, restart_ts in restart_rows:
        for err_pid, err_ts in error_rows:
            if (
                err_pid == pid
                and err_ts <= restart_ts
                and restart_ts - err_ts <= window_ns
            ):
                triples += 1
                affected.add(pid)

    return {
        "samples_scanned": samples_scanned,
        "errors_seen": errors_seen,
        "restarts_seen": restarts_seen,
        "correlated_triples": triples,
        "affected_pids": sorted(affected),
    }


def compute_expected() -> dict:
    pack = _load_pack()
    scenarios: dict[str, dict] = {}
    for row in pack["scenarios"]:
        sid = row["id"]
        window_ns = window_for_scenario(sid)
        counts = _scan_counts(Path(row["db_path"]), window_ns)
        scenarios[sid] = {
            **counts,
            "loops_run": row["loops"],
            "fd_delta": 0,
            "leak_reproduced": False,
            "root_cause": "none",
            "correlation_window_ns": window_ns,
        }
    return {"schema_version": 1, "scenarios": scenarios, "pack": pack}


EXPECTED_COUNTS = {
    "lane_alpha": {
        "samples_scanned": 4,
        "errors_seen": 4,
        "restarts_seen": 3,
        "affected_pids": [1001, 1002],
        "correlated_triples": 2,
    },
    "lane_beta": {
        "samples_scanned": 14,
        "errors_seen": 7,
        "restarts_seen": 2,
        "affected_pids": [2001, 2002],
        "correlated_triples": 4,
    },
    "lane_gamma": {
        "samples_scanned": 6,
        "errors_seen": 3,
        "restarts_seen": 4,
        "affected_pids": [3001, 3002, 3003],
        "correlated_triples": 3,
    },
    "lane_delta": {
        "samples_scanned": 3,
        "errors_seen": 3,
        "restarts_seen": 2,
        "affected_pids": [4001],
        "correlated_triples": 1,
    },
    "lane_epsilon": {
        "samples_scanned": 2,
        "errors_seen": 4,
        "restarts_seen": 3,
        "affected_pids": [5001, 5003],
        "correlated_triples": 3,
    },
    "lane_zeta": {
        "samples_scanned": 900,
        "errors_seen": 900,
        "restarts_seen": 900,
        "affected_pids": list(range(6000, 6900)),
        "correlated_triples": 900,
    },
    "lane_eta": {
        "samples_scanned": 0,
        "errors_seen": 1,
        "restarts_seen": 1,
        "affected_pids": [7001],
        "correlated_triples": 1,
    },
    "lane_iota": {
        "samples_scanned": 3,
        "errors_seen": 3,
        "restarts_seen": 3,
        "affected_pids": [4294967301, 8589934599, 9223372036854775000],
        "correlated_triples": 3,
    },
}
