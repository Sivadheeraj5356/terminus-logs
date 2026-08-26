from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
TESTS_DIR = Path(__file__).resolve().parent
RUNNER = ["php", str(ENV / "scripts/run_harden_cli.php")]
REPORT = APP / "out/harden_report.json"
RECOMPUTE = TESTS_DIR / "contract_recompute.py"
DB = APP / "data/embedserve_inventory.db"
PROFILE = "embedserve-default"
OPERATIVE_KEYS = (
    "model_sandbox_enabled",
    "allow_local_weight_files",
    "mmap_model_weights",
    "tokenizer_remote_code",
    "tokenizer_trust_remote_code",
)


def _reset_inventory() -> None:
    subprocess.run(
        ["python3", str(ENV / "data/generate_inventory.py")],
        check=True,
    )


def _reset_out() -> None:
    out = APP / "out"
    if out.exists():
        for child in out.iterdir():
            child.unlink()
    else:
        out.mkdir(parents=True, exist_ok=True)


def _run(*, reset_inventory: bool = True) -> dict:
    if reset_inventory:
        _reset_inventory()
    _reset_out()
    proc = subprocess.run(
        RUNNER + ["--profile", PROFILE, "--out", str(REPORT)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _expected() -> dict:
    proc = subprocess.run(
        ["python3", str(RECOMPUTE), PROFILE],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_report_matches_independent_recompute() -> None:
    """Harden JSON equals harness-side bundle, audit, and inventory derivation."""
    got = _run()
    want = _expected()
    for key in (
        "api_version",
        "profile",
        "opened_db_basename",
        "ops_section",
        "ops_digest",
        "lock_digest",
        "disabled_components",
        "inference_defaults_applied",
        "advisory_evidence_count",
        "sql_evidence",
    ):
        assert got[key] == want[key], key


def test_opened_inventory_is_active_catalog() -> None:
    """Report records the production inventory basename."""
    report = _run()
    assert report["opened_db_basename"] == "embedserve_inventory.db"


def test_ops_section_and_digest_from_section_eleven() -> None:
    """ops_section is 11 and ops_digest matches the operative register bytes."""
    report = _run()
    want = _expected()
    assert report["ops_section"] == 11
    assert report["ops_digest"] == want["ops_digest"]
    assert len(report["ops_digest"]) == len(want["ops_digest"])


def test_lock_digest_matches_tokenizer_lockfile() -> None:
    """lock_digest is the sixteen-char SHA-256 prefix of Cargo.lock."""
    report = _run()
    want = _expected()
    assert report["lock_digest"] == want["lock_digest"]


def test_vulnerable_rsa_component_disabled_in_sql() -> None:
    """Tokenizer rsa row is disabled with RUSTSEC evidence after harden."""
    _run()
    row = _query(
        """
        SELECT enabled, advisory_id
        FROM cargo_components
        WHERE profile_id = ? AND crate_name = 'rsa'
        """,
        (PROFILE,),
    )[0]
    assert row[0] == 0
    assert row[1] == "RUSTSEC-2023-0071"


def test_non_vulnerable_tokenizer_components_stay_enabled() -> None:
    """serde_json sidecar row remains enabled when audit is clean."""
    _run()
    row = _query(
        """
        SELECT enabled, advisory_id
        FROM cargo_components
        WHERE profile_id = ? AND crate_name = 'serde_json'
        """,
        (PROFILE,),
    )[0]
    assert row[0] == 1
    assert row[1] is None


def test_inference_defaults_applied_from_ratified_amendment() -> None:
    """Operative Section 11 defaults are applied in SQLite."""
    _run()
    want = _expected()
    for item in want["inference_defaults_applied"]:
        key = item["setting_key"]
        value = item["value"]
        row = _query(
            """
            SELECT current_value, hardened_value, applied
            FROM inference_defaults
            WHERE profile_id = ? AND setting_key = ?
            """,
            (PROFILE, key),
        )[0]
        assert row[0] == value
        assert row[1] == value
        assert row[2] == 1


def test_advisory_evidence_rows_persisted() -> None:
    """advisory_evidence contains one row per disabled advisory."""
    _run()
    rows = _query(
        """
        SELECT advisory_id, crate_name, severity
        FROM advisory_evidence
        WHERE profile_id = ?
        ORDER BY crate_name
        """,
        (PROFILE,),
    )
    assert len(rows) >= 1
    assert rows[0][0] == "RUSTSEC-2023-0071"
    assert rows[0][1] == "rsa"
    assert rows[0][2] in {"medium", "high", "low", "critical", "warning"}


def test_harden_run_row_records_digests() -> None:
    """harden_runs stores ops and lock digests with advisory count."""
    report = _run()
    rows = _query(
        """
        SELECT ops_digest, lock_digest, advisory_count
        FROM harden_runs
        WHERE profile_id = ?
        """,
        (PROFILE,),
    )
    assert len(rows) == 1
    assert rows[0][0] == report["ops_digest"]
    assert rows[0][1] == report["lock_digest"]
    assert rows[0][2] == report["advisory_evidence_count"]


def test_sql_evidence_counts_match_inventory_mutations() -> None:
    """sql_evidence component and default counts mirror SQLite updates."""
    report = _run()
    disabled = _query(
        """
        SELECT COUNT(*)
        FROM cargo_components
        WHERE profile_id = ? AND enabled = 0 AND advisory_id IS NOT NULL
        """,
        (PROFILE,),
    )[0][0]
    applied = _query(
        """
        SELECT COUNT(*)
        FROM inference_defaults
        WHERE profile_id = ? AND applied = 1
        """,
        (PROFILE,),
    )[0][0]
    assert report["sql_evidence"]["components_disabled"] == disabled
    assert report["sql_evidence"]["defaults_changed"] == applied
    assert applied == len(OPERATIVE_KEYS)


def test_disabled_components_sorted_in_report() -> None:
    """disabled_components is sorted by crate_name."""
    report = _run()
    names = [row["crate_name"] for row in report["disabled_components"]]
    assert names == sorted(names)


def test_back_to_back_runs_stable_on_fresh_inventory() -> None:
    """Repeated harden runs from seed inventory yield identical report payloads."""
    first = _run()
    second = _run()
    assert first == second
