#!/usr/bin/env python3

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent / "lineage.duckdb"

SCHEMA = """
CREATE TABLE feature_ledger (
    feature_name VARCHAR,
    feature_version VARCHAR,
    ledger_as_of TIMESTAMP,
    committed_at TIMESTAMP,
    source_table VARCHAR
);

CREATE TABLE run_manifest (
    run_id VARCHAR PRIMARY KEY,
    model_name VARCHAR,
    scenario VARCHAR
);

CREATE TABLE run_features (
    run_id VARCHAR,
    feature_name VARCHAR,
    feature_version VARCHAR
);

CREATE TABLE lineage_edges (
    child_feature VARCHAR,
    parent_feature VARCHAR
);
"""

FEATURES = [
    ("account_age_days", "v3", "2024-03-10 08:00:00", "2024-03-01 12:00:00", "core_users"),
    ("purchase_count_30d", "v1", "2024-05-12 11:00:00", "2024-05-01 10:00:00", "orders_ledger"),
    ("rolling_balance_7d", "v4", "2024-07-18 16:45:00", "2024-05-20 09:00:00", "balances_ledger"),
    ("session_length", "v2", "2024-05-15 10:00:00", "2024-07-10 12:00:00", "session_events"),
    ("tenure_days", "v1", "2024-06-01 00:00:00", "2024-07-15 08:00:00", "core_users"),
    ("credit_utilization", "v1", "2024-07-20 10:00:00", "2024-06-15 09:00:00", "balances_ledger"),
    ("signal_strength", "v2", "2024-04-01 00:00:00", "2024-08-01 00:00:00", "core_users"),
    ("signal_strength", "v3", "2024-08-10 12:00:00", "2024-04-01 00:00:00", "core_users"),
]

RUNS = [
    ("both_flags", "ranking_shadow", "both_flags"),
    ("clean", "fraud_guard_prod", "clean"),
    ("cutoff_boundary", "fraud_guard_prod", "cutoff_boundary"),
    ("dual_leak", "fraud_guard_prod", "dual_leak"),
    ("ingest_trap", "fraud_guard_prod", "ingest_trap"),
    ("leaking", "fraud_guard_prod", "leaking"),
    ("unapproved_model", "ranking_shadow", "unapproved_model"),
    ("version_bind", "fraud_guard_prod", "version_bind"),
]

RUN_FEATURES = [
    ("both_flags", "account_age_days", "v3"),
    ("both_flags", "rolling_balance_7d", "v4"),
    ("clean", "account_age_days", "v3"),
    ("clean", "purchase_count_30d", "v1"),
    ("cutoff_boundary", "tenure_days", "v1"),
    ("dual_leak", "account_age_days", "v3"),
    ("dual_leak", "credit_utilization", "v1"),
    ("dual_leak", "rolling_balance_7d", "v4"),
    ("ingest_trap", "session_length", "v2"),
    ("leaking", "account_age_days", "v3"),
    ("leaking", "rolling_balance_7d", "v4"),
    ("unapproved_model", "account_age_days", "v3"),
    ("unapproved_model", "purchase_count_30d", "v1"),
    ("version_bind", "signal_strength", "v2"),
]

EDGES = [
    ("purchase_count_30d", "orders_ledger"),
    ("rolling_balance_7d", "balances_ledger"),
    ("rolling_balance_7d", "purchase_count_30d"),
    ("account_age_days", "core_users"),
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    con.executemany(
        "INSERT INTO feature_ledger VALUES (?, ?, ?, ?, ?)",
        FEATURES,
    )
    con.executemany("INSERT INTO run_manifest VALUES (?, ?, ?)", RUNS)
    con.executemany(
        "INSERT INTO run_features VALUES (?, ?, ?)",
        RUN_FEATURES,
    )
    con.executemany(
        "INSERT INTO lineage_edges VALUES (?, ?)",
        EDGES,
    )
    con.close()


if __name__ == "__main__":
    main()
