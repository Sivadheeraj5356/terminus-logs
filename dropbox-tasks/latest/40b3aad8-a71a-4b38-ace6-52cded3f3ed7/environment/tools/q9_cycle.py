#!/usr/bin/env python3
"""Metamorphic stress driver for d9_run closure."""

from __future__ import annotations

import argparse
import hashlib
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ENV = Path("/app/environment")
OUT = Path("/app/output/inv_d9.yaml")
BUNDLE = ENV / "fixtures" / "set_a"
IDX = ENV / "data" / "idx_store.db"
DRIVER = ["node", str(ENV / "dist" / "d9_run.js")]


def row_digest(instance_uid: str, labels: list[int], weights: list[float]) -> str:
    label_csv = ",".join(str(x) for x in sorted(labels))
    weight_csv = ",".join(f"{w:.4f}" for w in weights)
    canon = f"{instance_uid}|{label_csv}|{weight_csv}"
    return hashlib.sha256(canon.encode()).hexdigest()


def make_tag(strengths: tuple[int, int, int], slice_id: int = 759) -> bytes:
    header = b"D759" + struct.pack(">I", slice_id) + b"\x00" * 120
    body = bytes(strengths)
    return header[:128] + body + b"\x00" * (140 - 128 - len(body))


def recovery() -> None:
    seg = ENV / "k2d" / "seg_v"
    seg.mkdir(parents=True, exist_ok=True)
    cursor = seg / "cursor.dat"
    if cursor.exists():
        cursor.unlink()
    (seg / ".reset").write_text("", encoding="utf-8")


def run_d9(fixture_dir: Path) -> dict:
    subprocess.run(
        DRIVER
        + [
            "--dump-dir",
            str(fixture_dir),
            "--idx-store",
            str(IDX),
            "--out",
            str(OUT),
        ],
        cwd=ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    return yaml.safe_load(OUT.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=759)
    parser.add_argument("--cycles", type=int, default=40)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    base_doc = run_d9(BUNDLE)
    assert base_doc["slice_id"] == 759
    for row in base_doc["rows"]:
        calc = row_digest(row["instance_uid"], row["labels"], row["weights"])
        if row["row_digest"] != calc:
            print("base digest mismatch", file=sys.stderr)
            return 1

    for round_idx in range(args.cycles):
        strengths = tuple(rng.randint(30, 40) for _ in range(3))
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            for name in ("uid_a", "uid_b", "uid_c"):
                src = BUNDLE / f"{name}.edi"
                (tdir / f"{name}.edi").write_bytes(src.read_bytes())
                (tdir / f"{name}.tag").write_bytes(make_tag(strengths))
            recovery()
            doc = run_d9(tdir)
        if doc["slice_id"] != 759:
            print(f"round {round_idx}: bad slice", file=sys.stderr)
            return 2
        for row in doc["rows"]:
            if row["o8_score"] < 0:
                print(f"round {round_idx}: negative o8", file=sys.stderr)
                return 3
            calc = row_digest(row["instance_uid"], row["labels"], row["weights"])
            if row["row_digest"] != calc:
                print(f"round {round_idx}: digest mismatch", file=sys.stderr)
                return 4
        if len(doc["rows"]) != 7:
            print(f"round {round_idx}: row count {len(doc['rows'])}", file=sys.stderr)
            return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
