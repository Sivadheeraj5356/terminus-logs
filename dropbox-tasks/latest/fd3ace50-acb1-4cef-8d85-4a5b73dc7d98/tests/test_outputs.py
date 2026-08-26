#!/usr/bin/env python3
"""VLAN Segmentation Enforcement Engine - Output Validation Tests.

Comprehensive per-flow violation assertions with positive and negative checks.
Uses the session-scoped `result` and `result_path` fixtures from conftest.py.
"""

import json
import os


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _violations_for_flow(result, flow_id):
    """Return all violations associated with a given flow_id."""
    return [v for v in result["violations"] if v["flow_id"] == flow_id]


def _flow_has_category(result, flow_id, category):
    """Check if a flow has at least one violation of the given category."""
    return any(
        v["category"] == category
        for v in result["violations"]
        if v["flow_id"] == flow_id
    )


def _flow_violation_severity(result, flow_id, category):
    """Return the severity of a specific flow+category violation."""
    for v in result["violations"]:
        if v["flow_id"] == flow_id and v["category"] == category:
            return v["severity"]
    return None


# ---------------------------------------------------------------------------
# Infrastructure tests
# ---------------------------------------------------------------------------

class TestInfrastructure:
    """Tests for build artifacts and output file existence."""

    def test_output_file_exists(self, result_path):
        """Verify the enforcement result file exists on disk and is valid JSON."""
        assert os.path.isfile(result_path), f"Output file missing: {result_path}"
        with open(result_path, "r") as f:
            data = json.load(f)
        assert isinstance(data, dict), "Output must be a JSON object"

    def test_binary_compiles(self):
        """Verify the C++ binary was compiled successfully (binary exists)."""
        binary_path = "/app/bin/vlan-segmentation-enforce"
        assert os.path.isfile(binary_path), (
            f"Compiled binary not found at {binary_path}. "
            "Ensure the project builds before running tests."
        )


# ---------------------------------------------------------------------------
# Schema and top-level structure tests
# ---------------------------------------------------------------------------

class TestSchema:
    """Tests verifying required keys and schema compliance."""

    def test_required_top_level_keys(self, result):
        """Verify all required top-level keys are present in the output."""
        required_keys = [
            "analysis_metadata",
            "summary",
            "violations",
            "trunk_configuration_findings",
            "native_vlan_analysis",
            "violation_breakdown",
        ]
        for key in required_keys:
            assert key in result, f"Missing required top-level key: {key}"

    def test_analysis_metadata_fields(self, result):
        """Verify analysis metadata contains expected fields with correct values."""
        meta = result["analysis_metadata"]
        assert "engine_version" in meta, "Missing engine_version"
        assert "total_flows_analyzed" in meta, "Missing total_flows_analyzed"
        assert "total_trunk_ports" in meta, "Missing total_trunk_ports"
        assert meta["total_flows_analyzed"] == 8, (
            f"Expected 8 flows analyzed, got {meta['total_flows_analyzed']}"
        )
        assert meta["total_trunk_ports"] == 4, (
            f"Expected 4 trunk ports, got {meta['total_trunk_ports']}"
        )

    def test_violations_have_required_fields(self, result):
        """Verify every violation entry contains all required schema fields."""
        required_fields = [
            "violation_id",
            "category",
            "severity",
            "description",
            "flow_id",
            "source_ip",
            "destination_ip",
            "source_vlan",
            "destination_vlan",
            "recommendation",
        ]
        for v in result["violations"]:
            for field in required_fields:
                assert field in v, (
                    f"Violation {v.get('violation_id', '?')} missing field: {field}"
                )

    def test_violation_ids_are_unique(self, result):
        """Verify all violation_id values are unique across the output."""
        ids = [v["violation_id"] for v in result["violations"]]
        assert len(ids) == len(set(ids)), "Duplicate violation_id values found"


# ---------------------------------------------------------------------------
# Per-flow positive violation assertions
# ---------------------------------------------------------------------------

class TestFlowF001:
    """F001: VLAN 100→200, 0x8100, outer=100, inner=200, dst_port=3389."""

    def test_f001_has_zone_violation(self, result):
        """F001 must trigger a zone_violation (crosses zone boundary)."""
        assert _flow_has_category(result, "F001", "zone_violation")

    def test_f001_zone_violation_severity_high(self, result):
        """F001 zone_violation must be severity=high (RDP to different zone)."""
        assert _flow_violation_severity(result, "F001", "zone_violation") == "high"

    def test_f001_has_acl_bypass(self, result):
        """F001 must trigger an acl_bypass (port 3389 blocked by ACL)."""
        assert _flow_has_category(result, "F001", "acl_bypass")

    def test_f001_acl_bypass_severity_high(self, result):
        """F001 acl_bypass must be severity=high."""
        assert _flow_violation_severity(result, "F001", "acl_bypass") == "high"

    def test_f001_violation_count(self, result):
        """F001 must produce exactly 2 violations."""
        assert len(_violations_for_flow(result, "F001")) == 2


class TestFlowF002:
    """F002: VLAN 100→300, 0x88A8, outer=1, inner=300, dst_port=22."""

    def test_f002_has_double_tagging(self, result):
        """F002 must trigger double_tagging (Q-in-Q with outer=native VLAN 1)."""
        assert _flow_has_category(result, "F002", "double_tagging")

    def test_f002_double_tagging_severity_critical(self, result):
        """F002 double_tagging must be severity=critical."""
        assert _flow_violation_severity(result, "F002", "double_tagging") == "critical"

    def test_f002_has_native_vlan_exploit(self, result):
        """F002 must trigger native_vlan_exploit (outer tag matches native VLAN)."""
        assert _flow_has_category(result, "F002", "native_vlan_exploit")

    def test_f002_native_vlan_exploit_severity_critical(self, result):
        """F002 native_vlan_exploit must be severity=critical."""
        assert _flow_violation_severity(result, "F002", "native_vlan_exploit") == "critical"

    def test_f002_violation_count(self, result):
        """F002 must produce exactly 2 violations."""
        assert len(_violations_for_flow(result, "F002")) == 2


class TestFlowF004:
    """F004: VLAN 200→400, 0x8100, outer=200, inner=400, dst_port=445."""

    def test_f004_has_zone_violation(self, result):
        """F004 must trigger a zone_violation (crosses zone boundary)."""
        assert _flow_has_category(result, "F004", "zone_violation")

    def test_f004_zone_violation_severity_high(self, result):
        """F004 zone_violation must be severity=high (SMB port 445)."""
        assert _flow_violation_severity(result, "F004", "zone_violation") == "high"

    def test_f004_has_acl_bypass(self, result):
        """F004 must trigger an acl_bypass (port 445 blocked by ACL)."""
        assert _flow_has_category(result, "F004", "acl_bypass")

    def test_f004_acl_bypass_severity_high(self, result):
        """F004 acl_bypass must be severity=high."""
        assert _flow_violation_severity(result, "F004", "acl_bypass") == "high"

    def test_f004_violation_count(self, result):
        """F004 must produce exactly 2 violations."""
        assert len(_violations_for_flow(result, "F004")) == 2


class TestFlowF005:
    """F005: VLAN 100→500, 0x8100, outer=1, inner=500, dst_port=1433."""

    def test_f005_has_double_tagging(self, result):
        """F005 must trigger double_tagging (outer=1 equals native VLAN)."""
        assert _flow_has_category(result, "F005", "double_tagging")

    def test_f005_double_tagging_severity_critical(self, result):
        """F005 double_tagging must be severity=critical."""
        assert _flow_violation_severity(result, "F005", "double_tagging") == "critical"

    def test_f005_has_native_vlan_exploit(self, result):
        """F005 must trigger native_vlan_exploit (outer tag matches native VLAN)."""
        assert _flow_has_category(result, "F005", "native_vlan_exploit")

    def test_f005_native_vlan_exploit_severity_critical(self, result):
        """F005 native_vlan_exploit must be severity=critical."""
        assert _flow_violation_severity(result, "F005", "native_vlan_exploit") == "critical"

    def test_f005_has_zone_violation(self, result):
        """F005 must trigger zone_violation (100→500 crosses zone boundary)."""
        assert _flow_has_category(result, "F005", "zone_violation")

    def test_f005_zone_violation_severity_medium(self, result):
        """F005 zone_violation must be severity=medium."""
        assert _flow_violation_severity(result, "F005", "zone_violation") == "medium"

    def test_f005_has_acl_bypass(self, result):
        """F005 must trigger acl_bypass (port 1433 blocked by ACL)."""
        assert _flow_has_category(result, "F005", "acl_bypass")

    def test_f005_acl_bypass_severity_high(self, result):
        """F005 acl_bypass must be severity=high."""
        assert _flow_violation_severity(result, "F005", "acl_bypass") == "high"

    def test_f005_violation_count(self, result):
        """F005 must produce exactly 4 violations (most complex flow)."""
        assert len(_violations_for_flow(result, "F005")) == 4


class TestFlowF007:
    """F007: VLAN 100→200, 0x8100, outer=100, inner=200, dst_port=53."""

    def test_f007_has_zone_violation(self, result):
        """F007 must trigger a zone_violation (crosses zone boundary)."""
        assert _flow_has_category(result, "F007", "zone_violation")

    def test_f007_zone_violation_severity_medium(self, result):
        """F007 zone_violation must be severity=medium (DNS port 53)."""
        assert _flow_violation_severity(result, "F007", "zone_violation") == "medium"

    def test_f007_has_acl_bypass(self, result):
        """F007 must trigger an acl_bypass."""
        assert _flow_has_category(result, "F007", "acl_bypass")

    def test_f007_acl_bypass_severity_high(self, result):
        """F007 acl_bypass must be severity=high."""
        assert _flow_violation_severity(result, "F007", "acl_bypass") == "high"

    def test_f007_violation_count(self, result):
        """F007 must produce exactly 2 violations."""
        assert len(_violations_for_flow(result, "F007")) == 2


class TestFlowF008:
    """F008: VLAN 400→100, 0x88A8, outer=1, inner=100, dst_port=44100."""

    def test_f008_has_double_tagging(self, result):
        """F008 must trigger double_tagging (Q-in-Q with outer=native VLAN 1)."""
        assert _flow_has_category(result, "F008", "double_tagging")

    def test_f008_double_tagging_severity_high(self, result):
        """F008 double_tagging must be severity=high."""
        assert _flow_violation_severity(result, "F008", "double_tagging") == "high"

    def test_f008_has_native_vlan_exploit(self, result):
        """F008 must trigger native_vlan_exploit (outer tag=1 matches native VLAN)."""
        assert _flow_has_category(result, "F008", "native_vlan_exploit")

    def test_f008_native_vlan_exploit_severity_critical(self, result):
        """F008 native_vlan_exploit must be severity=critical."""
        assert _flow_violation_severity(result, "F008", "native_vlan_exploit") == "critical"

    def test_f008_has_zone_violation(self, result):
        """F008 must trigger zone_violation (400→100 crosses zone boundary)."""
        assert _flow_has_category(result, "F008", "zone_violation")

    def test_f008_zone_violation_severity_medium(self, result):
        """F008 zone_violation must be severity=medium."""
        assert _flow_violation_severity(result, "F008", "zone_violation") == "medium"

    def test_f008_has_acl_bypass(self, result):
        """F008 must trigger acl_bypass."""
        assert _flow_has_category(result, "F008", "acl_bypass")

    def test_f008_acl_bypass_severity_high(self, result):
        """F008 acl_bypass must be severity=high."""
        assert _flow_violation_severity(result, "F008", "acl_bypass") == "high"

    def test_f008_violation_count(self, result):
        """F008 must produce exactly 4 violations."""
        assert len(_violations_for_flow(result, "F008")) == 4


# ---------------------------------------------------------------------------
# Negative assertions — flows/categories that must NOT appear
# ---------------------------------------------------------------------------

class TestNegativeAssertions:
    """Verify that skipped flows and incorrect categories are absent."""

    def test_f003_not_in_violations(self, result):
        """F003 (same VLAN 100→100) must NOT appear in any violation."""
        violations = _violations_for_flow(result, "F003")
        assert len(violations) == 0, (
            f"F003 is same-VLAN and should be skipped, but found {len(violations)} violations"
        )

    def test_f006_not_in_violations(self, result):
        """F006 (same VLAN 300→300) must NOT appear in any violation."""
        violations = _violations_for_flow(result, "F006")
        assert len(violations) == 0, (
            f"F006 is same-VLAN and should be skipped, but found {len(violations)} violations"
        )

    def test_f001_no_double_tagging(self, result):
        """F001 must NOT have double_tagging (outer=100 equals src_vlan, not native)."""
        assert not _flow_has_category(result, "F001", "double_tagging"), (
            "F001 should not have double_tagging: outer_tag=100=src_vlan, not outer=1"
        )

    def test_f001_no_native_vlan_exploit(self, result):
        """F001 must NOT have native_vlan_exploit (outer=100, not native VLAN 1)."""
        assert not _flow_has_category(result, "F001", "native_vlan_exploit"), (
            "F001 should not have native_vlan_exploit: outer_tag=100 != native VLAN 1"
        )

    def test_f004_no_double_tagging(self, result):
        """F004 must NOT have double_tagging (outer=200 equals src_vlan, not native)."""
        assert not _flow_has_category(result, "F004", "double_tagging"), (
            "F004 should not have double_tagging: outer_tag=200=src_vlan, not outer=1"
        )

    def test_f004_no_native_vlan_exploit(self, result):
        """F004 must NOT have native_vlan_exploit (outer=200, not native VLAN 1)."""
        assert not _flow_has_category(result, "F004", "native_vlan_exploit"), (
            "F004 should not have native_vlan_exploit: outer_tag=200 != native VLAN 1"
        )

    def test_f007_no_double_tagging(self, result):
        """F007 must NOT have double_tagging (outer=100 equals src_vlan, not native)."""
        assert not _flow_has_category(result, "F007", "double_tagging"), (
            "F007 should not have double_tagging: outer_tag=100=src_vlan, not outer=1"
        )

    def test_f007_no_native_vlan_exploit(self, result):
        """F007 must NOT have native_vlan_exploit (outer=100, not native VLAN 1)."""
        assert not _flow_has_category(result, "F007", "native_vlan_exploit"), (
            "F007 should not have native_vlan_exploit: outer_tag=100 != native VLAN 1"
        )


# ---------------------------------------------------------------------------
# Violation breakdown count tests
# ---------------------------------------------------------------------------

class TestViolationBreakdown:
    """Verify exact per-category counts in violation_breakdown."""

    def test_double_tagging_count(self, result):
        """Exactly 3 double_tagging violations (F002, F005, F008)."""
        assert result["violation_breakdown"]["double_tagging"] == 3

    def test_native_vlan_exploit_count(self, result):
        """Exactly 3 native_vlan_exploit violations (F002, F005, F008)."""
        assert result["violation_breakdown"]["native_vlan_exploit"] == 3

    def test_zone_violation_count(self, result):
        """Exactly 5 zone_violation violations (F001, F004, F005, F007, F008)."""
        assert result["violation_breakdown"]["zone_violation"] == 5

    def test_acl_bypass_count(self, result):
        """Exactly 5 acl_bypass violations (F001, F004, F005, F007, F008)."""
        assert result["violation_breakdown"]["acl_bypass"] == 5

    def test_breakdown_matches_actual_violations(self, result):
        """Verify breakdown totals match actual violation list counts."""
        breakdown = result["violation_breakdown"]
        for category, expected_count in breakdown.items():
            actual = len([
                v for v in result["violations"] if v["category"] == category
            ])
            assert actual == expected_count, (
                f"Breakdown says {category}={expected_count} but found {actual} in violations list"
            )


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

class TestSummary:
    """Verify exact summary statistics."""

    def test_total_violations(self, result):
        """Summary total_violations must equal 16."""
        assert result["summary"]["total_violations"] == 16

    def test_critical_count(self, result):
        """Summary critical must equal 5."""
        assert result["summary"]["critical"] == 5

    def test_high_count(self, result):
        """Summary high must equal 8."""
        assert result["summary"]["high"] == 8

    def test_medium_count(self, result):
        """Summary medium must equal 3."""
        assert result["summary"]["medium"] == 3

    def test_low_count(self, result):
        """Summary low must equal 0."""
        assert result["summary"]["low"] == 0

    def test_enforcement_status_failed(self, result):
        """Enforcement status must be FAILED when critical violations exist."""
        assert result["summary"]["enforcement_status"] == "FAILED"

    def test_summary_counts_add_up(self, result):
        """Verify critical + high + medium + low equals total_violations."""
        s = result["summary"]
        computed = s["critical"] + s["high"] + s["medium"] + s["low"]
        assert computed == s["total_violations"], (
            f"Sum of severities ({computed}) != total_violations ({s['total_violations']})"
        )


# ---------------------------------------------------------------------------
# Trunk configuration findings
# ---------------------------------------------------------------------------

class TestTrunkFindings:
    """Verify trunk configuration findings count and content."""

    def test_trunk_findings_total_count(self, result):
        """Exactly 8 trunk configuration findings (4 native mismatch + 4 DTP)."""
        findings = result["trunk_configuration_findings"]
        assert len(findings) == 8, (
            f"Expected 8 trunk findings, got {len(findings)}"
        )

    def test_native_vlan_mismatch_findings_count(self, result):
        """Exactly 4 Native VLAN mismatch findings."""
        findings = result["trunk_configuration_findings"]
        native_findings = [
            f for f in findings if "Native VLAN" in f.get("finding", "")
        ]
        assert len(native_findings) == 4, (
            f"Expected 4 Native VLAN mismatch findings, got {len(native_findings)}"
        )

    def test_dtp_findings_count(self, result):
        """Exactly 4 DTP-related findings."""
        findings = result["trunk_configuration_findings"]
        dtp_findings = [
            f for f in findings if "DTP" in f.get("finding", "")
        ]
        assert len(dtp_findings) == 4, (
            f"Expected 4 DTP findings, got {len(dtp_findings)}"
        )

    def test_native_vlan_mismatch_references_core_switch(self, result):
        """Native VLAN mismatch findings must reference core-switch-01."""
        findings = result["trunk_configuration_findings"]
        native_findings = [
            f for f in findings if "Native VLAN" in f.get("finding", "")
        ]
        texts = " ".join(f.get("finding", "") for f in native_findings)
        assert "core-switch-01" in texts, (
            "Native VLAN mismatch findings should reference core-switch-01"
        )

    def test_native_vlan_mismatch_references_access_switch_02(self, result):
        """Native VLAN mismatch findings must reference access-switch-02."""
        findings = result["trunk_configuration_findings"]
        native_findings = [
            f for f in findings if "Native VLAN" in f.get("finding", "")
        ]
        texts = " ".join(f.get("finding", "") for f in native_findings)
        assert "access-switch-02" in texts, (
            "Native VLAN mismatch findings should reference access-switch-02"
        )

    def test_native_vlan_mismatch_references_access_switch_03(self, result):
        """Native VLAN mismatch findings must reference access-switch-03."""
        findings = result["trunk_configuration_findings"]
        native_findings = [
            f for f in findings if "Native VLAN" in f.get("finding", "")
        ]
        texts = " ".join(f.get("finding", "") for f in native_findings)
        assert "access-switch-03" in texts, (
            "Native VLAN mismatch findings should reference access-switch-03"
        )

    def test_dtp_findings_reference_all_trunk_ports(self, result):
        """DTP findings must reference all 4 trunk ports."""
        findings = result["trunk_configuration_findings"]
        dtp_findings = [
            f for f in findings if "DTP" in f.get("finding", "")
        ]
        assert len(dtp_findings) == 4, "Need 4 DTP findings for 4 trunk ports"


# ---------------------------------------------------------------------------
# Native VLAN analysis
# ---------------------------------------------------------------------------

class TestNativeVlanAnalysis:
    """Verify native VLAN analysis exact values."""

    def test_mismatch_detected_true(self, result):
        """native_vlan_analysis.mismatch_detected must be True."""
        nva = result["native_vlan_analysis"]
        assert nva["mismatch_detected"] is True

    def test_all_consistent_false(self, result):
        """native_vlan_analysis.all_consistent must be False."""
        nva = result["native_vlan_analysis"]
        assert nva["all_consistent"] is False

    def test_risk_level_critical(self, result):
        """native_vlan_analysis.risk_level must be 'critical'."""
        nva = result["native_vlan_analysis"]
        assert nva["risk_level"] == "critical"


# ---------------------------------------------------------------------------
# Cross-VLAN flow count validation
# ---------------------------------------------------------------------------

class TestCrossVlanFlowCoverage:
    """Verify exactly 6 cross-VLAN flows produced violations."""

    def test_exactly_six_cross_vlan_flows_have_violations(self, result):
        """Only F001, F002, F004, F005, F007, F008 should appear in violations."""
        flow_ids = set(v["flow_id"] for v in result["violations"])
        expected_flows = {"F001", "F002", "F004", "F005", "F007", "F008"}
        assert flow_ids == expected_flows, (
            f"Expected violations from flows {expected_flows}, got {flow_ids}"
        )

    def test_total_violation_list_length(self, result):
        """The violations list must contain exactly 16 entries."""
        assert len(result["violations"]) == 16, (
            f"Expected 16 violations in list, got {len(result['violations'])}"
        )


# ---------------------------------------------------------------------------
# All flow+category combinations exist (without hardcoding violation_id)
# ---------------------------------------------------------------------------

class TestAllFlowCategoryCombinations:
    """Verify every expected (flow_id, category) pair exists in violations."""

    EXPECTED_COMBINATIONS = [
        ("F001", "zone_violation"),
        ("F001", "acl_bypass"),
        ("F002", "double_tagging"),
        ("F002", "native_vlan_exploit"),
        ("F004", "zone_violation"),
        ("F004", "acl_bypass"),
        ("F005", "double_tagging"),
        ("F005", "native_vlan_exploit"),
        ("F005", "zone_violation"),
        ("F005", "acl_bypass"),
        ("F007", "zone_violation"),
        ("F007", "acl_bypass"),
        ("F008", "double_tagging"),
        ("F008", "native_vlan_exploit"),
        ("F008", "zone_violation"),
        ("F008", "acl_bypass"),
    ]

    def test_all_expected_combinations_present(self, result):
        """Every expected (flow_id, category) pair must exist in violations."""
        actual_combinations = set(
            (v["flow_id"], v["category"]) for v in result["violations"]
        )
        for flow_id, category in self.EXPECTED_COMBINATIONS:
            assert (flow_id, category) in actual_combinations, (
                f"Missing expected violation: flow={flow_id}, category={category}"
            )

    def test_no_unexpected_combinations(self, result):
        """No violations beyond the 16 expected (flow_id, category) pairs."""
        actual_combinations = set(
            (v["flow_id"], v["category"]) for v in result["violations"]
        )
        expected = set(self.EXPECTED_COMBINATIONS)
        unexpected = actual_combinations - expected
        assert len(unexpected) == 0, (
            f"Unexpected violation combinations found: {unexpected}"
        )
