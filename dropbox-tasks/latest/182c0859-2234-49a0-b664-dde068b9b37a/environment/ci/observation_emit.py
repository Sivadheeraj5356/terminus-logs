#!/usr/bin/env python3
"""Emit lto_observation.json from the latest build state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lto.summary_read import summary_hash_map
from lto.module_index import all_modules
from probes.symbol_probe import linked_symbol_set
from probes.vtable_check import probe_values


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(pass_name: str, append: bool, out_path: Path) -> None:
    work = Path("/app/work")
    binary = work / "bin" / "matrix_app"
    modules = all_modules()
    payload: dict[str, object] = {"report_version": 1, "matrix": [], "incremental_transcript": []}
    if append and out_path.is_file():
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    row = {
        "scenario": pass_name,
        "profile": "release",
        "summary_hash": summary_hash_map(work / "lto", modules),
        "linked_symbol_set": linked_symbol_set(binary),
        "binary_sha256": _sha256(binary),
        "probe": probe_values(binary),
    }
    matrix = payload.setdefault("matrix", [])
    assert isinstance(matrix, list)
    matrix.append(row)
    transcript = payload.setdefault("incremental_transcript", [])
    assert isinstance(transcript, list)
    transcript.append({"pass": pass_name, "row": row})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pass", dest="pass_name", required=True)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--out", default="/app/output/lto_observation.json")
    args = parser.parse_args()
    record(args.pass_name, args.append, Path(args.out))


if __name__ == "__main__":
    main()
