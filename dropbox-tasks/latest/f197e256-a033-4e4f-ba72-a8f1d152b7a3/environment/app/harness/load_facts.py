#!/usr/bin/env python3
"""Emit JSON facts for a single workstation ID from the DuckDB inventory.

Usage: load_facts.py <workstation_id>

Prints a single-line JSON object with the exact keys the Rego library
consumes.  Failure to find the row is exit code 3 with a JSON error on
stderr; the harness relies on the exit code, not the message.
"""
from __future__ import annotations

import json
import sys

import duckdb

DB = "/app/inventory/workstations.duckdb"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: load_facts.py <workstation_id>", file=sys.stderr)
        return 2
    ws_id = argv[1]
    con = duckdb.connect(DB, read_only=True)
    cur = con.execute(
        "SELECT * FROM v_workstation WHERE id = ?", [ws_id]
    )
    columns = [d[0] for d in cur.description]
    row = cur.fetchone()
    con.close()
    if row is None:
        print(json.dumps({"error": "not_found", "id": ws_id}), file=sys.stderr)
        return 3
    obj = dict(zip(columns, row))
    # Normalise any non-JSON-serialisable scalars (DuckDB returns Python
    # native ints/strs/bools by default; the loop below coerces the few
    # remaining edge cases: numpy scalars via .item(), and datetime.date /
    # datetime.datetime instances via str().
    import datetime as _dt
    for k, v in list(obj.items()):
        if hasattr(v, "item"):
            obj[k] = v.item()
        elif isinstance(v, (_dt.date, _dt.datetime)):
            obj[k] = str(v)
    # Ensure the fixture workload has the actual file path attached so the
    # Rego library can key media-scratch actions off the extension.
    workload = obj["workload"]
    obj["fixture_path"] = f"/app/fixtures/{workload}/sample.{workload}"
    print(json.dumps({"workstation": obj}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
