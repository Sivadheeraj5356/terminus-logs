"""Milestone 2 tests — pipeline order and tier adjustment basis."""

from test_helpers import (
    assert_production_inputs_unchanged,
    coinsurance_base,
    expected_indemnity_share,
    expected_m2_tier_adjustment,
    load_config,
    load_report,
    money,
    policy_source_by_id,
    regenerate_report,
    round_money,
)

M2_EDGE_IDS = [
    "COI-009",
    "COI-013",
    "COI-016",
    "COI-018",
    "COI-021",
    "COI-027",
    "COI-028",
    "COI-029",
    "COI-031",
]
M2_INDEMNITY_SHARE_IDS = ("COI-009", "COI-016", "COI-018")


def test_production_inputs_unchanged_m2():
    """Reject edits to production input data or config before scoring milestone 2."""
    assert_production_inputs_unchanged()


def test_milestone2_indemnity_share_from_coinsurance_base():
    """Verify indemnityShare scales from coinsuranceBase rather than raw grossIncurred."""
    regenerate_report()
    report, config, sources = load_report(), load_config(), policy_source_by_id()
    by_id = {r["id"]: r for r in report["policies"]}
    for pid in M2_INDEMNITY_SHARE_IDS:
        assert money(by_id[pid]["indemnityShare"]) == expected_indemnity_share(sources[pid], config), pid


def test_milestone2_tier_adjustment_post_quota_basis():
    """Verify tier adjustment uses indemnityShare minus quota credit on quota lines."""
    regenerate_report()
    report, config, sources = load_report(), load_config(), policy_source_by_id()
    by_id = {r["id"]: r for r in report["policies"]}
    threshold = money(config["coinsurance.threshold.quota"])
    for pid in M2_EDGE_IDS:
        row, src = by_id[pid], sources[pid]
        assert money(row["tierAdjustmentAmount"]) == expected_m2_tier_adjustment(row, src, config), pid
        qc = money(row["quotaCreditAmount"])
        ind, ar = money(row["indemnityShare"]), money(row["adjustmentRate"])
        if (
            src["policyTier"].lower() in ("premium", "plus")
            and coinsurance_base(src) >= threshold
            and qc > 0
        ):
            assert money(row["tierAdjustmentAmount"]) < round_money(ind * ar)
