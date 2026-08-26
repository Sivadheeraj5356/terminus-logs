#!/usr/bin/env python3
"""Build /app/inventory/workstations.duckdb from workstations.csv.

The DuckDB schema mirrors the CSV columns 1:1 so the harness can query it
with a single SELECT.  We create a stable primary key on workstation_id
and a materialized view `v_workstation` that renames the physical
columns to the exact JSON keys the Rego library expects, so a
downstream operator can `SELECT to_json(v_workstation)` without doing
any renaming client-side.
"""
from __future__ import annotations

import os
import sys

import duckdb

APP = "/app"
CSV = os.path.join(APP, "inventory", "workstations.csv")
DB = os.path.join(APP, "inventory", "workstations.duckdb")


def build() -> None:
    if not os.path.exists(CSV):
        print(f"missing csv: {CSV}", file=sys.stderr)
        sys.exit(2)
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)
    # Force the schema explicitly so DuckDB does not mis-parse the kernel
    # release column (looks like a dot-separated date) or the ptrace/suid
    # columns (mixed int-like values).
    con.execute(
        """
        CREATE TABLE workstations (
            workstation_id VARCHAR,
            hostname VARCHAR,
            chip_family VARCHAR,
            kernel_release VARCHAR,
            fixture_workload VARCHAR,
            ptrace_scope INTEGER,
            core_pattern VARCHAR,
            suid_dumpable INTEGER,
            coredump_conf_present BOOLEAN,
            in_debug_group BOOLEAN,
            in_media_group BOOLEAN,
            ulimit_core_soft VARCHAR,
            ulimit_core_hard VARCHAR,
            scratch_perms VARCHAR,
            scratch_owner VARCHAR,
            scratch_group VARCHAR,
            fs_immutable BOOLEAN
        );
        INSERT INTO workstations SELECT * FROM read_csv(
            ?,
            header=True,
            columns={
                'workstation_id':'VARCHAR',
                'hostname':'VARCHAR',
                'chip_family':'VARCHAR',
                'kernel_release':'VARCHAR',
                'fixture_workload':'VARCHAR',
                'ptrace_scope':'INTEGER',
                'core_pattern':'VARCHAR',
                'suid_dumpable':'INTEGER',
                'coredump_conf_present':'BOOLEAN',
                'in_debug_group':'BOOLEAN',
                'in_media_group':'BOOLEAN',
                'ulimit_core_soft':'VARCHAR',
                'ulimit_core_hard':'VARCHAR',
                'scratch_perms':'VARCHAR',
                'scratch_owner':'VARCHAR',
                'scratch_group':'VARCHAR',
                'fs_immutable':'BOOLEAN'
            }
        );
        """,
        [CSV],
    )
    # Enforce PK-like uniqueness (DuckDB will reject dupes on the CTAS above
    # only via a follow-up unique index).
    con.execute("CREATE UNIQUE INDEX ux_ws_id ON workstations(workstation_id);")
    # View with the exact keys the Rego harness expects.
    con.execute(
        """
        CREATE VIEW v_workstation AS
        SELECT
            workstation_id      AS id,
            hostname            AS hostname,
            chip_family         AS chip,
            kernel_release      AS kernel,
            fixture_workload    AS workload,
            ptrace_scope        AS ptrace_scope,
            core_pattern        AS core_pattern,
            suid_dumpable       AS suid_dumpable,
            coredump_conf_present AS coredump_conf,
            in_debug_group      AS in_debug_group,
            in_media_group      AS in_media_group,
            ulimit_core_soft    AS core_soft,
            ulimit_core_hard    AS core_hard,
            scratch_perms       AS scratch_perms,
            scratch_owner       AS scratch_owner,
            scratch_group       AS scratch_group,
            fs_immutable        AS scratch_immutable
        FROM workstations
        ORDER BY workstation_id;
        """
    )
    n = con.execute("SELECT COUNT(*) FROM workstations").fetchone()[0]
    con.close()
    print(f"built {DB} with {n} workstation rows")


if __name__ == "__main__":
    build()
