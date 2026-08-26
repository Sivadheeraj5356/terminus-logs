#!/usr/bin/env python3
"""Matrix driver — orchestrates telreplay across seeded scenarios."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

APP = Path("/app")
BIN = APP / "bin" / "telreplay"
PACK = APP / "data" / "scenarios.json"
OUT_DIR = APP / "output"
MATRIX = OUT_DIR / "matrix_report.json"
SEAL = OUT_DIR / "report_seal.bin"


def crc32c(data: bytes) -> int:
    poly = 0x82F63B78
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def build_seal(matrix_digest: str, reports: list[dict]) -> bytes:
    prefix = hashlib.sha256(matrix_digest.encode("utf-8")).digest()[:16]
    fd_sum = sum(int(r["fd_delta"]) for r in reports)
    count = len(reports)
    head = prefix + struct.pack("<q", fd_sum) + struct.pack(">Q", count)
    crc = crc32c(head)
    return head + struct.pack("<I", crc) + b"\x00\x00\x00\x00"


def main() -> int:
    if not BIN.is_file():
        print("missing telreplay binary", file=sys.stderr)
        return 2

    pack = json.loads(PACK.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    scenario_reports: list[dict] = []
    for row in pack["scenarios"]:
        sid = row["id"]
        proc = subprocess.run(
            [
                str(BIN),
                "--db",
                row["db_path"],
                "--scenario",
                sid,
                "--loops",
                str(row["loops"]),
            ],
            capture_output=True,
            text=True,
        )
        single = APP / "output" / ".single_report.json"
        if not single.is_file():
            print(proc.stderr or proc.stdout, file=sys.stderr)
            return proc.returncode or 2
        scenario_reports.append(json.loads(single.read_text(encoding="utf-8")))
        if proc.returncode != 0:
            print(f"scenario {sid} failed rc={proc.returncode}", file=sys.stderr)
            return proc.returncode

    scenarios_obj: dict[str, dict] = {}
    body_hashes: list[str] = []
    for rep in scenario_reports:
        sid = rep["scenario_id"]
        body = {k: v for k, v in rep.items() if k != "body_sha256"}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
        rep_out = dict(body)
        rep_out["body_sha256"] = body_sha
        scenarios_obj[sid] = rep_out
        body_hashes.append(body_sha)

    matrix_digest = hashlib.sha256("".join(body_hashes).encode("utf-8")).hexdigest()
    matrix = {
        "matrix_digest": matrix_digest,
        "schema_version": 1,
        "scenarios": scenarios_obj,
    }
    MATRIX.write_text(
        json.dumps(matrix, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    SEAL.write_bytes(build_seal(matrix_digest, scenario_reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
