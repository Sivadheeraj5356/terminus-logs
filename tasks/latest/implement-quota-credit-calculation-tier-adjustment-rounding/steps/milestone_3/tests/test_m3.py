"""Milestone 3 tests — rounding schedule and amount-based premium rules."""

from test_helpers import (
    assert_production_inputs_unchanged,
    expected_report,
    load_report,
    money,
    regenerate_report,
)


def test_production_inputs_unchanged_m3():
    """Reject edits to production input data or config before scoring milestone 3."""
    assert_production_inputs_unchanged()


def test_milestone3_quota_and_holdback_rounding():
    """Verify quota credit and premium holdback rounding on documented edge policies."""
    regenerate_report()
    report, expected = load_report(), expected_report()
    by_id = {r["id"]: r for r in report["policies"]}
    exp_by_id = {r["id"]: r for r in expected["policies"]}
    edges = {
        "COI-009": ["premiumHoldbackAmount"],
        "COI-011": ["tierAdjustmentAmount", "premiumHoldbackAmount"],
        "COI-014": ["premiumHoldbackAmount"],
        "COI-015": ["quotaCreditAmount", "premiumHoldbackAmount"],
        "COI-017": ["quotaCreditAmount", "premiumHoldbackAmount"],
        "COI-019": ["premiumHoldbackAmount"],
        "COI-020": ["premiumHoldbackAmount"],
        "COI-022": ["quotaCreditAmount", "premiumHoldbackAmount"],
        "COI-027": ["quotaCreditAmount", "premiumHoldbackAmount"],
        "COI-028": ["quotaCreditAmount", "tierAdjustmentAmount"],
        "COI-031": ["quotaCreditAmount", "premiumHoldbackAmount"],
    }
    for pid, fields in edges.items():
        for field in fields:
            assert money(by_id[pid][field]) == money(exp_by_id[pid][field])


def test_milestone3_net_recovery_all_policies():
    """Verify netRecovery for every eligible policy matches the documented formula."""
    regenerate_report()
    report, expected = load_report(), expected_report()
    exp_by_id = {r["id"]: r for r in expected["policies"]}
    for row in report["policies"]:
        policy_id = row["id"]
        assert "netRecovery" in row, f"{policy_id} missing netRecovery"
        assert money(row["netRecovery"]) == money(exp_by_id[policy_id]["netRecovery"]), policy_id
