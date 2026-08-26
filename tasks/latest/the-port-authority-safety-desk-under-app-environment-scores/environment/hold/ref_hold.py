#!/usr/bin/env python3
"""Hold-store parity helper for score export."""

import hashlib
import sqlite3
import sys
from pathlib import Path

SQL = Path(__file__).with_name("hold_ledger.sql")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parity_fp(cover_hex: str, merge_hex: str, block_hex: str) -> str:
    import tempfile

    sql = SQL.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "hold.db"
        conn = sqlite3.connect(db)
        conn.executescript(sql)
        for kind, val in [("cover", cover_hex), ("merge", merge_hex), ("block", block_hex)]:
            conn.execute("INSERT INTO digests(kind,val) VALUES(?,?)", (kind, val))
        rows = conn.execute("SELECT row FROM v_hold_ordered").fetchall()
        conn.close()
    joined = "\n".join(r[0] for r in rows)
    return sha256_hex(joined.encode("utf-8"))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: ref_hold.py parity_fp <cover> <merge> <block>")
    if sys.argv[1] == "parity_fp":
        print(parity_fp(sys.argv[2], sys.argv[3], sys.argv[4]))
        return
    raise SystemExit(f"unknown command: {sys.argv[1]}")


if __name__ == "__main__":
    main()
