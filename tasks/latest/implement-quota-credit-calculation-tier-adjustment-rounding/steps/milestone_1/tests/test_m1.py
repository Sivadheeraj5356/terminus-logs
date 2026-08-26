"""Milestone 1 tests — config loader and eligibility."""

from test_helpers import (
    CONFIG_PATH,
    assert_production_inputs_unchanged,
    eligible_policy_ids,
    load_report,
    regenerate_report,
)

EXPECTED_ELIGIBLE_COUNT = 26


def test_production_inputs_unchanged_m1():
    """Reject edits to production input data or config before scoring milestone 1."""
    assert_production_inputs_unchanged()


def test_milestone1_report_has_policies_and_summary():
    """Verify the report exposes the documented top-level keys for this milestone."""
    regenerate_report()
    report = load_report()
    assert "policies" in report
    assert "summary" in report
    assert isinstance(report["policies"], list)
    assert isinstance(report["summary"], dict)
    assert "policyCount" in report["summary"]


def test_milestone1_eligible_recovery_count():
    """Verify the batch includes exactly the eligible policy rows from production input."""
    regenerate_report()
    report = load_report()
    ids = {row["id"] for row in report["policies"]}
    assert report["summary"]["policyCount"] == EXPECTED_ELIGIBLE_COUNT
    assert ids == eligible_policy_ids()
    assert "COI-003" in ids
    assert "COI-006" not in ids
    assert "COI-026" not in ids
    assert "COI-030" not in ids


def test_milestone1_minimum_threshold_loaded_from_properties():
    """Verify eligibility reads minimum.policy.amount dynamically from the properties file."""
    assert_production_inputs_unchanged()
    original_config = CONFIG_PATH.read_text(encoding="utf-8")
    try:
        CONFIG_PATH.write_text(
            original_config.replace(
                "minimum.policy.amount=1500.00", "minimum.policy.amount=5000.00"
            ),
            encoding="utf-8",
        )
        regenerate_report(force=True)
        report = load_report()
        assert report["summary"]["policyCount"] == 21
        assert "COI-005" not in {row["id"] for row in report["policies"]}
    finally:
        CONFIG_PATH.write_text(original_config, encoding="utf-8")
    assert_production_inputs_unchanged()
