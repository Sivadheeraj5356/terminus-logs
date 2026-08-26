"""Milestone 4 tests — net formula, schema, Gson spacing."""

import re

from test_helpers import (
    OUTPUT_PATH,
    assert_production_inputs_unchanged,
    assert_report_matches_expected,
    expected_report,
    load_report,
    money,
    regenerate_report,
)

ROW_MONEY_FIELDS = [
    "grossIncurred",
    "deductibleAmount",
    "coinsuranceRate",
    "indemnityShare",
    "processingFeeAmount",
    "adjustmentRate",
    "tierAdjustmentAmount",
    "quotaCreditAmount",
    "premiumHoldbackAmount",
    "netRecovery",
]

SUMMARY_MONEY_FIELDS = [
    "totalIndemnityShare",
    "totalProcessingFee",
    "totalTierAdjustment",
    "totalQuotaCredit",
    "totalPremiumHoldback",
    "totalRecovery",
]


def test_production_inputs_unchanged_m4():
    """Reject edits to production input data or config before scoring milestone 4."""
    assert_production_inputs_unchanged()


def test_milestone4_report_schema_and_totals():
    """Verify report schema, summary totals, and sort order against the production oracle."""
    regenerate_report(force=True)
    report, expected = load_report(), expected_report()
    assert "generatedAt" in report
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", report["generatedAt"]
    )
    assert_report_matches_expected(report, expected)
    ids = [r["id"] for r in report["policies"]]
    assert ids == [r["id"] for r in expected["policies"]] and ids[0] == "COI-015"


def test_milestone4_gson_pretty_print_spacing():
    """Ensure Gson pretty-print spacing, nesting, and numeric padding in raw JSON."""
    regenerate_report(force=True)
    raw = OUTPUT_PATH.read_text(encoding="utf-8")
    report = load_report()
    sample = report["policies"][0]
    value = f"{money(sample['netRecovery']):.2f}"
    assert re.search(rf'"netRecovery": {re.escape(value)}', raw)
    assert not re.search(r'"[A-Za-z]+":\S', raw), (
        "Found compact colon without trailing space; Gson pretty-print requires a space after each colon"
    )
    assert re.search(r'"policies": \[\n', raw), "policies array must open on a new line"
    assert re.search(r'"summary": \{\n', raw), "summary object must open on a new line"
    assert re.search(r'\n    \{\n      "id":', raw), (
        "policy rows must use Gson nested object indentation"
    )
    assert re.search(r'\n  "summary": \{\n    "policyCount":', raw), (
        "summary block must use Gson nested object indentation"
    )
    assert not re.search(r'"policies": \[{', raw), "policies array must not use compact opening"
    for field in ROW_MONEY_FIELDS:
        assert not re.search(rf'"{field}": -?\d+,', raw), field
        assert not re.search(rf'"{field}": -?\d+\.\d(?!\d),', raw), field


def test_milestone4_money_fields_have_two_decimal_places():
    """Ensure serialized JSON uses spaced numeric literals with exactly two decimal places."""
    regenerate_report(force=True)
    raw = OUTPUT_PATH.read_text(encoding="utf-8")
    report = load_report()

    for row in report["policies"]:
        for field in ROW_MONEY_FIELDS:
            value = f"{money(row[field]):.2f}"
            assert re.search(rf'"{field}": {re.escape(value)}', raw), row["id"]

    for field in SUMMARY_MONEY_FIELDS:
        value = f"{money(report['summary'][field]):.2f}"
        assert re.search(rf'"{field}": {re.escape(value)}', raw)
