#!/usr/bin/env python3
"""Authoring-time bootstrap for idx_store.db and ORDERS dump bytes."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIX = ROOT / "fixtures" / "set_a"
SLICE = 759
ZONE = 759

ROWS = [
    ("uid_a", 110, 11, "set_a", "101,102", bytes([33, 33, 34])),
    ("uid_b", 120, 12, "set_a", "201", bytes([50, 50, 50])),
    ("uid_c", 100, 10, "set_a", "100", bytes([33, 33, 33])),
]

DECOY_ROW = ("uid_d", 130, 12, "set_a", "202", bytes([40, 40, 40]))


def make_tag(strengths: bytes, slice_id: int = SLICE) -> bytes:
    header = b"D759" + struct.pack(">I", slice_id) + b"\x00" * 120
    return header[:128] + strengths + b"\x00" * (140 - 128 - len(strengths))


def edi_for(uid: str, seeds: str) -> str:
    parts = seeds.split(",")
    nad = "+".join(parts)
    return f"UNH+{uid}'\nBGM+759'\nNAD+{nad}'\nUNT+3'\n"


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    FIX.mkdir(parents=True, exist_ok=True)
    db_path = DATA / "idx_store.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE series_rows (
          instance_uid TEXT,
          mesh_id INTEGER,
          class_code INTEGER,
          series_id TEXT,
          seed_labels TEXT,
          tag_blob BLOB,
          slice_id INTEGER,
          zone_id INTEGER
        )
        """
    )
    for uid, mesh, cls, series, leaves, strengths in ROWS:
        blob = make_tag(strengths)
        (FIX / f"{uid}.edi").write_text(edi_for(uid, leaves), encoding="utf-8")
        conn.execute(
            "INSERT INTO series_rows VALUES (?,?,?,?,?,?,?,?)",
            (uid, mesh, cls, series, leaves, blob, SLICE, ZONE),
        )
    uid, mesh, cls, series, leaves, strengths = DECOY_ROW
    decoy_blob = make_tag(strengths, 999)
    (FIX / f"{uid}.edi").write_text(edi_for(uid, leaves), encoding="utf-8")
    conn.execute(
        "INSERT INTO series_rows VALUES (?,?,?,?,?,?,?,?)",
        (uid, mesh, cls, series, leaves, decoy_blob, 999, ZONE),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
