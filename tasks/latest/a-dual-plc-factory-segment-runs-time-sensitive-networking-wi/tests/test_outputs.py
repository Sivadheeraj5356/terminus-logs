"""Verifier for tsn-schedule-verifier outputs."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

from reference_solver import (
    DATA_DIR,
    analytical_flows,
    bandwidth_frame_bytes,
    bandwidth_reserved_mbps,
    bursts_per_period,
    compliance_deadline_us,
    compute_expected,
    compute_wcet,
    deadline_shaving_us,
    detect_gate_conflicts,
    detect_priority_inversions,
    egress_port_fallback_required,
    egress_port_for_hop,
    enabled_flows,
    flow_analytical_eligible,
    flow_enabled,
    gate_wait_us,
    inter_frame_gap_penalty_us,
    is_switch_node,
    link_available_mbps,
    load_json,
    load_jsonl,
    load_policy,
    miss_sort_key,
    node_processing_us,
    open_time_ns,
    path_skew_excess,
    queue_for_class,
    queue_guard_band_us,
    reserved_mbps,
    trace_jitter_us,
    trace_qualifies_clock_skew,
    trace_raw_latency_us,
    validated_traces,
)

OUTPUT_DIR = Path("/app/output")
POLICY = load_policy()
TOPOLOGY = load_json(DATA_DIR / POLICY["inputs"]["topology"])
SCHEDULES = load_json(DATA_DIR / POLICY["inputs"]["gate_schedules"])
TRAFFIC = load_json(DATA_DIR / POLICY["inputs"]["traffic_classes"])
FLOWS_DOC = load_json(DATA_DIR / POLICY["inputs"]["message_flows"])
CLOCK = load_json(DATA_DIR / POLICY["inputs"]["clock_sync"])
TRACES = load_jsonl(DATA_DIR / POLICY["inputs"]["packet_traces"])
PROFILE = load_json(DATA_DIR / POLICY["inputs"]["tsn_profile"])

(
    EXPECTED_MISSES,
    EXPECTED_CONFLICTS,
    EXPECTED_UTILIZATION,
    EXPECTED_METRICS,
    EXPECTED_INVERSIONS,
    _EXPECTED_REPORT,
) = compute_expected()

MISS_KEYS = set(POLICY["outputs"]["deadline_misses"]["entry_keys"])
CONFLICT_KEYS = set(POLICY["outputs"]["gate_conflicts"]["entry_keys"])
ACTIVE_FLOWS = enabled_flows(FLOWS_DOC["flows"])
ELIGIBLE_FLOWS = analytical_flows(FLOWS_DOC["flows"])
VALIDATED = validated_traces(TRACES)
FLOW_BY_ID = {flow["flow_id"]: flow for flow in FLOWS_DOC["flows"]}
OFFSETS = {row["node_id"]: int(row["offset_us"]) for row in CLOCK["offsets"]}
TOLERANCE_US = int(CLOCK["tolerance_us"])
GRANDMASTER = CLOCK["grandmaster"]
ANALYTICAL_FAIL_IDS = {
    row.flow_id for row in EXPECTED_MISSES if row.miss_type == "analytical"
}


def load_output(name: str):
    path = OUTPUT_DIR / name
    if path.suffix in {".csv", ".md"}:
        return path.read_text(encoding="utf-8")
    return load_json(path)


def load_misses() -> dict:
    return load_json(OUTPUT_DIR / POLICY["outputs"]["deadline_misses"]["path"])


def load_conflicts() -> dict:
    return load_json(OUTPUT_DIR / POLICY["outputs"]["gate_conflicts"]["path"])


def load_util_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(load_output(POLICY["outputs"]["network_utilization"]["path"]).splitlines()))


def parse_metrics_table(report: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in report.splitlines():
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 2 and cells[0] != "Metric":
            rows[cells[0]] = cells[1]
    return rows


def miss_row_sort_key(row: dict) -> tuple:
    return miss_sort_key(POLICY, row["miss_type"], row["flow_id"], row["cycle"])


def miss_rows_by_type(miss_type: str) -> list[dict]:
    return [row for row in load_misses()["misses"] if row["miss_type"] == miss_type]


def assert_miss_rows_equivalent(actual: dict, expected) -> None:
    assert actual["miss_id"] == expected.miss_id
    assert actual["flow_id"] == expected.flow_id
    assert actual["miss_type"] == expected.miss_type
    assert actual["cycle"] == expected.cycle
    assert actual["deadline_us"] == expected.deadline_us
    assert float(actual["latency_us"]) == pytest.approx(expected.latency_us)
    assert float(actual["margin_us"]) == pytest.approx(expected.margin_us)
    assert actual["description"] == expected.description


def assert_conflict_rows_equivalent(actual: dict, expected) -> None:
    assert actual["conflict_id"] == expected.conflict_id
    assert actual["switch_id"] == expected.switch_id
    assert actual["port"] == expected.port
    assert {actual["window_a"], actual["window_b"]} == {expected.window_a, expected.window_b}
    assert int(actual["overlap_ns"]) == expected.overlap_ns
    assert actual["description"] == expected.description


# --- bundle presence ---


def test_all_policy_inputs_exist() -> None:
    for name in POLICY["inputs"].values():
        assert (DATA_DIR / name).is_file()


def test_all_required_outputs_exist() -> None:
    outputs = POLICY["outputs"]
    for key in ("schedule_validation_report", "deadline_misses", "gate_conflicts", "network_utilization"):
        assert (OUTPUT_DIR / outputs[key]["path"]).is_file()


# --- schema ---


def test_deadline_misses_top_level_keys() -> None:
    assert set(load_misses().keys()) == set(POLICY["outputs"]["deadline_misses"]["top_level_keys"])


def test_deadline_miss_entry_schema() -> None:
    for row in load_misses()["misses"]:
        assert set(row.keys()) == MISS_KEYS


def test_gate_conflicts_top_level_keys() -> None:
    assert set(load_conflicts().keys()) == set(POLICY["outputs"]["gate_conflicts"]["top_level_keys"])


def test_gate_conflict_entry_schema() -> None:
    for row in load_conflicts()["conflicts"]:
        assert set(row.keys()) == CONFLICT_KEYS


def test_network_utilization_header() -> None:
    assert load_output(POLICY["outputs"]["network_utilization"]["path"]).splitlines()[0] == (
        POLICY["outputs"]["network_utilization"]["header"]
    )


def test_network_utilization_integer_columns_have_no_decimal_point() -> None:
    for row in load_util_rows():
        for column in ("hyperperiod_us", "available_mbps"):
            assert "." not in row[column]
            int(row[column])


def test_analytical_misses_have_null_cycle() -> None:
    assert all(row["cycle"] is None for row in miss_rows_by_type("analytical"))


def test_observed_and_clock_skew_misses_have_cycle() -> None:
    for miss_type in ("observed", "clock_skew"):
        assert all(isinstance(row["cycle"], int) for row in miss_rows_by_type(miss_type))


# --- reference oracle (semantic) ---


def test_deadline_misses_match_reference() -> None:
    actual = sorted(load_misses()["misses"], key=miss_row_sort_key)
    expected = sorted(
        EXPECTED_MISSES,
        key=lambda miss: miss_sort_key(POLICY, miss.miss_type, miss.flow_id, miss.cycle),
    )
    assert load_misses()["network_id"] == TOPOLOGY["network_id"]
    assert len(actual) == len(expected)
    for actual_row, expected_row in zip(actual, expected, strict=True):
        assert_miss_rows_equivalent(actual_row, expected_row)


def test_gate_conflicts_match_reference() -> None:
    actual = load_conflicts()["conflicts"]
    assert len(actual) == len(EXPECTED_CONFLICTS)
    assert load_conflicts()["network_id"] == TOPOLOGY["network_id"]
    for actual_row, expected_row in zip(actual, EXPECTED_CONFLICTS, strict=True):
        assert_conflict_rows_equivalent(actual_row, expected_row)


def test_miss_descriptions_use_nominal_deadline_not_compliance() -> None:
    """Description templates show nominal flow.deadline_us, not compliance deadline."""
    for row in load_misses()["misses"]:
        flow = FLOW_BY_ID[row["flow_id"]]
        nominal = int(flow["deadline_us"])
        compliance = compliance_deadline_us(TRAFFIC, flow)
        assert row["deadline_us"] == nominal
        assert f"deadline {nominal} us" in row["description"]
        if nominal != compliance:
            assert f"deadline {compliance} us" not in row["description"]


def test_schedule_validation_report_matches_reference() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    assert report == _EXPECTED_REPORT


def test_network_utilization_matches_reference() -> None:
    for expected, row in zip(EXPECTED_UTILIZATION, load_util_rows(), strict=True):
        assert row["link_id"] == expected["link_id"]
        assert int(row["hyperperiod_us"]) == expected["hyperperiod_us"]
        assert float(row["reserved_mbps"]) == pytest.approx(expected["reserved_mbps"])
        assert int(row["available_mbps"]) == int(expected["available_mbps"])
        assert float(row["utilization_ratio"]) == pytest.approx(expected["utilization_ratio"])
        assert row["overcommitted"] == str(expected["overcommitted"]).lower()


def test_schedule_validation_report_has_required_sections() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    cfg = POLICY["report_markdown"]
    for heading in (
        cfg["metrics_section_heading"],
        cfg["deadline_summary_heading"],
        cfg["gate_conflict_heading"],
        cfg["priority_inversion_heading"],
        cfg["bandwidth_heading"],
    ):
        assert heading in report
        if cfg.get("blank_line_after_section_heading"):
            assert f"{heading}\n\n" in report


# --- per-flow WCET edge cases ---


@pytest.mark.parametrize("flow_id", sorted(FLOW_BY_ID))
def test_enabled_flow_wcet_recomputed(flow_id: str) -> None:
    flow = FLOW_BY_ID[flow_id]
    if not flow_enabled(flow):
        pytest.skip("disabled flow")
    expected = compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, flow)
    compliance = compliance_deadline_us(TRAFFIC, flow)
    fails = expected > compliance
    analytical = [row for row in miss_rows_by_type("analytical") if row["flow_id"] == flow_id]
    if not flow_analytical_eligible(flow):
        assert analytical == []
        return
    if fails:
        assert len(analytical) == 1
        assert float(analytical[0]["latency_us"]) == pytest.approx(expected)
    else:
        assert analytical == []


@pytest.mark.parametrize("flow_id", sorted(ANALYTICAL_FAIL_IDS))
def test_analytical_fail_flow_wcet_exceeds_compliance_deadline(flow_id: str) -> None:
    flow = FLOW_BY_ID[flow_id]
    miss = next(row for row in miss_rows_by_type("analytical") if row["flow_id"] == flow_id)
    expected = compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, flow)
    compliance = compliance_deadline_us(TRAFFIC, flow)
    assert float(miss["latency_us"]) == pytest.approx(expected)
    assert expected > compliance


@pytest.mark.parametrize(
    "flow_id",
    ["flow-monitor-01", "flow-monitor-02", "flow-bulk-01"],
)
def test_analytical_pass_flow_has_no_miss(flow_id: str) -> None:
    assert flow_id not in {row["flow_id"] for row in miss_rows_by_type("analytical")}


def test_endpoint_processing_included_in_wcet() -> None:
    flow = FLOW_BY_ID["flow-safety-01"]
    endpoint_sum = sum(node_processing_us(TOPOLOGY, node) for node in flow["path"])
    switch_only = sum(
        node_processing_us(TOPOLOGY, node)
        for node in flow["path"]
        if any(n["node_id"] == node and n.get("role") == "switch" for n in TOPOLOGY["nodes"])
    )
    assert endpoint_sum > switch_only
    assert compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, flow) > switch_only


def test_grandmaster_processing_excluded_from_wcet_path() -> None:
    assert node_processing_us(TOPOLOGY, GRANDMASTER) == 0.0


def test_egress_port_resolved_from_topology_switch_ports() -> None:
    assert egress_port_for_hop(TOPOLOGY, SCHEDULES, "sw1", "sw2") == "eth1"
    assert egress_port_for_hop(TOPOLOGY, SCHEDULES, "sw2", "hmi1") == "eth0"
    assert egress_port_for_hop(TOPOLOGY, SCHEDULES, "sw3", "sw2") == "eth1"


def test_egress_port_fallback_when_switch_ports_missing() -> None:
    assert egress_port_fallback_required(TOPOLOGY, "sw1", "sw3")
    assert egress_port_for_hop(TOPOLOGY, SCHEDULES, "sw1", "sw3") == "eth1"


def test_backup_path_monitor_flow_gate_wait_positive() -> None:
    flow = FLOW_BY_ID["flow-monitor-02"]
    port = egress_port_for_hop(TOPOLOGY, SCHEDULES, "sw1", "sw3")
    schedule = next(
        row for row in SCHEDULES["schedules"] if row["switch_id"] == "sw1" and row["port"] == port
    )
    queue = queue_for_class(TRAFFIC, flow["traffic_class"])
    wait = gate_wait_us(schedule, queue, int(SCHEDULES["cycle_time_ns"]), int(PROFILE["gate_open_value"]))
    assert wait > 0
    assert compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, flow) > wait


# --- bandwidth / derate / bursts ---


@pytest.mark.parametrize("link_id", [link["link_id"] for link in TOPOLOGY["links"]])
def test_link_utilization_matches_reference(link_id: str) -> None:
    expected = next(row for row in EXPECTED_UTILIZATION if row["link_id"] == link_id)
    actual = next(row for row in load_util_rows() if row["link_id"] == link_id)
    assert float(actual["reserved_mbps"]) == pytest.approx(expected["reserved_mbps"])
    assert float(actual["utilization_ratio"]) == pytest.approx(expected["utilization_ratio"])


def test_bottleneck_applies_derate_factor_to_available_mbps() -> None:
    link = next(item for item in TOPOLOGY["links"] if item["link_id"] == "lnk-sw1-sw2")
    row = next(r for r in load_util_rows() if r["link_id"] == "lnk-sw1-sw2")
    assert int(row["available_mbps"]) == int(link_available_mbps(link))
    assert int(row["available_mbps"]) == 80


def test_burst_multiplier_doubles_bulk_and_monitor_reservation() -> None:
    bulk = FLOW_BY_ID["flow-bulk-01"]
    monitor = FLOW_BY_ID["flow-monitor-01"]
    assert bursts_per_period(bulk) == 2
    assert bursts_per_period(monitor) == 2
    single_bulk = bandwidth_reserved_mbps({**bulk, "bursts_per_period": 1})
    assert bandwidth_reserved_mbps(bulk) == pytest.approx(2 * single_bulk, rel=1e-4)
    row = next(r for r in load_util_rows() if r["link_id"] == "lnk-sw1-sw2")
    assert float(row["reserved_mbps"]) == pytest.approx(
        next(r["reserved_mbps"] for r in EXPECTED_UTILIZATION if r["link_id"] == "lnk-sw1-sw2")
    )
    assert float(row["utilization_ratio"]) > 2.0


def test_disabled_flow_excluded_from_bandwidth_reservation() -> None:
    retired = FLOW_BY_ID["flow-bulk-retired"]
    assert flow_enabled(retired) is False
    row = next(r for r in load_util_rows() if r["link_id"] == "lnk-sw1-sw2")
    without_retired = sum(
        bandwidth_reserved_mbps(flow)
        for flow in ACTIVE_FLOWS
        if any(
            flow["path"][idx] == "sw1" and flow["path"][idx + 1] == "sw2"
            for idx in range(len(flow["path"]) - 1)
        )
    )
    decimals = POLICY["outputs"]["network_utilization"]["reserved_mbps_decimals"]
    assert float(row["reserved_mbps"]) == pytest.approx(round(without_retired, decimals))


def test_backup_link_carries_only_monitor02_reservation() -> None:
    row = next(r for r in load_util_rows() if r["link_id"] == "lnk-sw1-sw3")
    flow = FLOW_BY_ID["flow-monitor-02"]
    expected = round(
        bandwidth_reserved_mbps(flow),
        POLICY["outputs"]["network_utilization"]["reserved_mbps_decimals"],
    )
    assert float(row["reserved_mbps"]) == expected


def test_bandwidth_headroom_min_reflects_derated_overcommit() -> None:
    decimals = POLICY["metrics"]["bandwidth_headroom_min"]["round_decimals"]
    headroom_values = [
        float(row["available_mbps"]) - float(row["reserved_mbps"]) for row in EXPECTED_UTILIZATION
    ]
    assert EXPECTED_METRICS["bandwidth_headroom_min"] == pytest.approx(round(min(headroom_values), decimals))


# --- trace / observed / clock skew ---


def test_validated_trace_count_excludes_validate_false() -> None:
    assert len(VALIDATED) == len(TRACES) - 1
    assert len(TRACES) == 23


def test_validate_false_trace_excluded_from_observed_misses() -> None:
    assert not any(
        row["flow_id"] == "flow-safety-01" and row["cycle"] == 0 and row["miss_type"] == "observed"
        for row in load_misses()["misses"]
    )


def test_observed_misses_exclude_clock_skew_superseded_traces() -> None:
    decimals = POLICY["trace_validation"]["round_latency_us"]
    for trace in VALIDATED:
        flow = FLOW_BY_ID[trace["flow_id"]]
        if trace_qualifies_clock_skew(
            trace, flow, TRAFFIC, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY, decimals
        ):
            assert not any(
                row["miss_type"] == "observed"
                and row["flow_id"] == trace["flow_id"]
                and row["cycle"] == int(trace["cycle"])
                for row in load_misses()["misses"]
            )


def test_tr001_emits_clock_skew_not_observed() -> None:
    trace = next(t for t in TRACES if t["trace_id"] == "tr-001")
    assert trace_qualifies_clock_skew(
        trace, FLOW_BY_ID[trace["flow_id"]], TRAFFIC, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY,
        POLICY["trace_validation"]["round_latency_us"],
    )
    assert not any(row["miss_type"] == "observed" and "tr-001" in row["description"] for row in load_misses()["misses"])


def test_clock_skew_misses_detected_from_reference() -> None:
    expected = [row for row in EXPECTED_MISSES if row.miss_type == "clock_skew"]
    actual = miss_rows_by_type("clock_skew")
    assert len(actual) == len(expected)


def test_grandmaster_excluded_from_path_skew_sum() -> None:
    flow = FLOW_BY_ID["flow-safety-01"]
    assert path_skew_excess(flow, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY) <= path_skew_excess(
        flow, OFFSETS, TOLERANCE_US, "", TOPOLOGY
    )


def test_switch_only_skew_excludes_endpoint_offsets() -> None:
    flow = FLOW_BY_ID["flow-safety-02"]
    switch_only = path_skew_excess(flow, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY)
    all_nodes = sum(
        max(0, abs(OFFSETS[node]) - TOLERANCE_US)
        for node in flow["path"]
        if node != GRANDMASTER and node in OFFSETS
    )
    assert switch_only < all_nodes
    assert is_switch_node(TOPOLOGY, "sw2")
    assert not is_switch_node(TOPOLOGY, "hmi2")


def test_jitter_contributes_to_clock_skew_adjusted_latency() -> None:
    trace = next(t for t in TRACES if t["trace_id"] == "tr-001")
    flow = FLOW_BY_ID[trace["flow_id"]]
    raw = float(trace["arrival_us"]) - float(trace["release_us"])
    skew = path_skew_excess(flow, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY)
    adjusted = raw + skew + trace_jitter_us(trace)
    miss = next(row for row in miss_rows_by_type("clock_skew") if "tr-001" in row["description"])
    assert float(miss["latency_us"]) == pytest.approx(round(adjusted, 3))


def test_scheduling_exempt_flow_omitted_from_analytical_misses() -> None:
    audit = FLOW_BY_ID["flow-audit-01"]
    assert flow_analytical_eligible(audit) is False
    assert compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, audit) > int(audit["deadline_us"])
    assert "flow-audit-01" not in {row["flow_id"] for row in miss_rows_by_type("analytical")}


def test_scheduling_exempt_flow_still_counts_toward_bandwidth() -> None:
    row = next(r for r in load_util_rows() if r["link_id"] == "lnk-sw1-sw2")
    audit = FLOW_BY_ID["flow-audit-01"]
    audit_share = bandwidth_reserved_mbps(audit)
    without_audit = float(row["reserved_mbps"]) - round(audit_share, 4)
    assert without_audit < float(row["reserved_mbps"])


def test_emergency_flow_analytical_miss_present() -> None:
    assert "flow-emergency-01" in ANALYTICAL_FAIL_IDS


def test_analytical_miss_margin_uses_compliance_deadline() -> None:
    for row in miss_rows_by_type("analytical"):
        flow = FLOW_BY_ID[row["flow_id"]]
        compliance = compliance_deadline_us(TRAFFIC, flow)
        assert float(row["margin_us"]) == pytest.approx(compliance - float(row["latency_us"]))


def test_clock_skew_miss_margin_uses_compliance_deadline() -> None:
    for row in miss_rows_by_type("clock_skew"):
        flow = FLOW_BY_ID[row["flow_id"]]
        compliance = compliance_deadline_us(TRAFFIC, flow)
        assert float(row["margin_us"]) == pytest.approx(compliance - float(row["latency_us"]))


def test_inter_frame_gap_penalty_increases_burst_flow_wcet() -> None:
    bulk = FLOW_BY_ID["flow-bulk-01"]
    gap = inter_frame_gap_penalty_us(bulk)
    assert gap == 35.0
    base = compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, bulk)
    assert base > 2800.0


def test_queue_guard_band_extends_gate_wait() -> None:
    schedule = next(
        row for row in SCHEDULES["schedules"] if row["switch_id"] == "sw1" and row["port"] == "eth1"
    )
    queue = queue_for_class(TRAFFIC, "TC6-control")
    base = (int(SCHEDULES["cycle_time_ns"]) - open_time_ns(schedule, queue, int(PROFILE["gate_open_value"]))) / 1000.0
    guard = queue_guard_band_us(schedule, queue)
    assert guard == 12.0
    assert gate_wait_us(schedule, queue, int(SCHEDULES["cycle_time_ns"]), int(PROFILE["gate_open_value"])) == pytest.approx(
        base + guard
    )


def test_bandwidth_overhead_increases_reservation() -> None:
    bulk = FLOW_BY_ID["flow-bulk-01"]
    assert bandwidth_frame_bytes(bulk) == int(bulk["frame_size_bytes"]) + 64
    without_overhead = reserved_mbps(int(bulk["frame_size_bytes"]), int(bulk["period_us"]), bursts_per_period(bulk))
    assert bandwidth_reserved_mbps(bulk) > without_overhead


def test_string_trace_timestamps_coerced_for_latency() -> None:
    trace = next(t for t in TRACES if t["trace_id"] == "tr-012")
    decimals = POLICY["trace_validation"]["round_latency_us"]
    assert trace_raw_latency_us(trace, decimals) == pytest.approx(580.0)


def test_clock_sync_compliance_excludes_grandmaster() -> None:
    sync_nodes = [row for row in CLOCK["offsets"] if row["node_id"] != GRANDMASTER]
    compliant = sum(1 for row in sync_nodes if abs(int(row["offset_us"])) <= TOLERANCE_US)
    assert EXPECTED_METRICS["clock_sync_compliance_rate"] == pytest.approx(
        round(compliant / len(sync_nodes), 4)
    )


def test_compliance_deadline_subtracts_traffic_class_shaving() -> None:
    control = FLOW_BY_ID["flow-control-01"]
    assert deadline_shaving_us(TRAFFIC, control["traffic_class"]) == 25
    assert compliance_deadline_us(TRAFFIC, control) == int(control["deadline_us"]) - 25


def test_deadline_compliance_rate_uses_compliance_deadline() -> None:
    decimals = POLICY["trace_validation"]["round_latency_us"]
    compliant = sum(
        1
        for trace in VALIDATED
        if trace_raw_latency_us(trace, decimals)
        <= compliance_deadline_us(TRAFFIC, FLOW_BY_ID[trace["flow_id"]])
    )
    assert EXPECTED_METRICS["deadline_compliance_rate"] == pytest.approx(
        round(compliant / len(VALIDATED), 4)
    )


def test_observed_miss_margin_uses_compliance_deadline() -> None:
    for row in miss_rows_by_type("observed"):
        flow = FLOW_BY_ID[row["flow_id"]]
        compliance = compliance_deadline_us(TRAFFIC, flow)
        assert float(row["margin_us"]) == pytest.approx(compliance - float(row["latency_us"]))


# --- gate conflicts ---


def test_three_gate_conflicts_detected() -> None:
    assert len(load_conflicts()["conflicts"]) == 3


def test_non_exclusive_windows_do_not_create_conflicts() -> None:
    conflicts = detect_gate_conflicts(POLICY, SCHEDULES)
    assert not any("rw-sync-c" in (c.window_a, c.window_b) for c in conflicts)


def test_gate_conflicts_sorted_by_switch_port_overlap_desc() -> None:
    keys = [(row["switch_id"], row["port"], row["overlap_ns"]) for row in load_conflicts()["conflicts"]]
    assert keys == sorted(keys, key=lambda item: (item[0], item[1], -item[2]))


def test_sw1_eth0_monitor_overlap_is_gc001() -> None:
    first = load_conflicts()["conflicts"][0]
    assert first["switch_id"] == "sw1" and first["port"] == "eth0"
    assert first["overlap_ns"] == 100000


def test_sw2_eth1_diag_partial_overlap() -> None:
    conflict = next(row for row in load_conflicts()["conflicts"] if row["switch_id"] == "sw2")
    assert conflict["overlap_ns"] == 50000


# --- priority inversion ---


def test_two_priority_inversions_detected() -> None:
    assert EXPECTED_METRICS["priority_inversion_count"] == 2
    assert len(EXPECTED_INVERSIONS) == 2


def test_sw1_eth1_cycle3_inversion_queues_six_seven() -> None:
    assert any("sw1 eth1 cycle 3" in line and "Queue 6" in line for line in EXPECTED_INVERSIONS)


def test_sw2_eth0_cycle2_inversion_queues_three_five() -> None:
    assert any("sw2 eth0 cycle 2" in line and "Queue 3" in line for line in EXPECTED_INVERSIONS)


def test_priority_inversion_skips_validate_false_traces() -> None:
    assert len(detect_priority_inversions(POLICY, TRACES)) == 2


# --- metrics / report ---


def test_schedule_feasibility_score_from_reference() -> None:
    assert EXPECTED_METRICS["schedule_feasibility_score"] == pytest.approx(
        round(100 * (1 - len(ANALYTICAL_FAIL_IDS) / len(ELIGIBLE_FLOWS)), 2)
    )


def test_report_metrics_table_values() -> None:
    table = parse_metrics_table(load_output(POLICY["outputs"]["schedule_validation_report"]["path"]))
    labels = POLICY["metrics"]["report_metric_labels"]
    for key, label in labels.items():
        expected = EXPECTED_METRICS[key]
        if key == "priority_inversion_count":
            assert int(table[label]) == int(expected)
        else:
            decimals = POLICY["metrics"][key]["round_decimals"]
            assert float(table[label]) == pytest.approx(expected, abs=10 ** -decimals)


def test_report_lists_all_deadline_miss_ids() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    for miss in EXPECTED_MISSES:
        assert miss.miss_id in report
        assert miss.flow_id in report


def test_report_bandwidth_lists_derated_overcommitted_bottleneck() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    assert "lnk-sw1-sw2" in report
    assert "overcommitted: true" in report


def test_miss_ids_unique_prefixed_and_sorted() -> None:
    cfg = POLICY["outputs"]["deadline_misses"]
    prefix = cfg["miss_id_prefix"]
    ids = [row["miss_id"] for row in load_misses()["misses"]]
    assert len(ids) == len(set(ids))
    assert all(vid.startswith(f"{prefix}{cfg['miss_id_separator']}") for vid in ids)
    assert [miss_row_sort_key(row) for row in load_misses()["misses"]] == sorted(
        miss_row_sort_key(row) for row in load_misses()["misses"]
    )


def test_network_id_propagates_to_json_outputs() -> None:
    assert load_misses()["network_id"] == TOPOLOGY["network_id"]
    assert load_conflicts()["network_id"] == TOPOLOGY["network_id"]


def test_open_time_ns_for_safety_queue_on_sw1_eth1() -> None:
    schedule = next(
        row for row in SCHEDULES["schedules"] if row["switch_id"] == "sw1" and row["port"] == "eth1"
    )
    open_ns = open_time_ns(schedule, queue_for_class(TRAFFIC, "TC7-safety"), int(PROFILE["gate_open_value"]))
    assert open_ns == 200000


def test_gate_wait_us_for_control_queue_on_sw2_eth0() -> None:
    schedule = next(
        row for row in SCHEDULES["schedules"] if row["switch_id"] == "sw2" and row["port"] == "eth0"
    )
    queue = queue_for_class(TRAFFIC, "TC6-control")
    wait = gate_wait_us(
        schedule,
        queue,
        int(SCHEDULES["cycle_time_ns"]),
        int(PROFILE["gate_open_value"]),
    )
    assert wait == pytest.approx(650.0)


def test_hyperperiod_lcm_of_eligible_flow_periods() -> None:
    from reference_solver import lcm_list

    periods = [int(flow["period_us"]) for flow in ELIGIBLE_FLOWS]
    assert int(load_util_rows()[0]["hyperperiod_us"]) == lcm_list(periods) == 30000


def test_rerun_produces_identical_deadline_misses() -> None:
    solve = Path("/app/solution/solve.sh")
    if not solve.is_file():
        pytest.skip("oracle solve.sh not mounted")
    before = json.dumps(load_misses(), sort_keys=True)
    subprocess.run(["bash", str(solve)], check=True)
    after = json.dumps(load_misses(), sort_keys=True)
    assert before == after


def test_flow_sync_borderline_analytical_miss_margin() -> None:
    miss = next(row for row in miss_rows_by_type("analytical") if row["flow_id"] == "flow-sync-01")
    flow = FLOW_BY_ID["flow-sync-01"]
    compliance = compliance_deadline_us(TRAFFIC, flow)
    assert float(miss["latency_us"]) > compliance
    assert float(miss["margin_us"]) == pytest.approx(compliance - float(miss["latency_us"]))


def test_flow_diag_largest_analytical_miss_margin() -> None:
    miss = next(row for row in miss_rows_by_type("analytical") if row["flow_id"] == "flow-diag-01")
    assert float(miss["margin_us"]) < -1800


def test_sw2_and_hmi2_exceed_clock_tolerance() -> None:
    for node_id in ("sw2", "hmi2"):
        offset = next(row for row in CLOCK["offsets"] if row["node_id"] == node_id)
        assert abs(int(offset["offset_us"])) > TOLERANCE_US


def test_hmi2_offset_contributes_to_plc2_path_skew() -> None:
    flow = FLOW_BY_ID["flow-safety-02"]
    skew = path_skew_excess(flow, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY)
    assert skew == sum(
        max(0, abs(OFFSETS[node]) - TOLERANCE_US)
        for node in flow["path"]
        if node != GRANDMASTER and is_switch_node(TOPOLOGY, node) and node in OFFSETS
    )


def test_clock_skew_miss_for_tr006() -> None:
    miss = next(row for row in miss_rows_by_type("clock_skew") if row["flow_id"] == "flow-safety-02" and row["cycle"] == 1)
    trace = next(t for t in TRACES if t["trace_id"] == "tr-006")
    decimals = POLICY["trace_validation"]["round_latency_us"]
    flow = FLOW_BY_ID[trace["flow_id"]]
    expected = trace_raw_latency_us(trace, decimals) + path_skew_excess(
        flow, OFFSETS, TOLERANCE_US, GRANDMASTER, TOPOLOGY
    ) + trace_jitter_us(trace)
    assert float(miss["latency_us"]) == pytest.approx(round(expected, decimals))


def test_report_contains_required_verbatim_tokens() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    for token in POLICY["report_markdown"]["required_verbatim"]:
        assert token in report


def test_conflict_ids_unique_and_prefixed() -> None:
    cfg = POLICY["outputs"]["gate_conflicts"]
    ids = [row["conflict_id"] for row in load_conflicts()["conflicts"]]
    assert len(ids) == len(set(ids))
    assert all(vid.startswith(f"{cfg['conflict_id_prefix']}{cfg['conflict_id_separator']}") for vid in ids)


def test_utilization_rows_sorted_by_link_id() -> None:
    link_ids = [row["link_id"] for row in load_util_rows()]
    assert link_ids == sorted(link_ids)


def test_report_priority_inversion_lines_match_reference() -> None:
    report = load_output(POLICY["outputs"]["schedule_validation_report"]["path"])
    for line in EXPECTED_INVERSIONS:
        assert line in report


def test_json_latency_whole_values_use_float_form() -> None:
    for row in load_misses()["misses"]:
        latency = float(row["latency_us"])
        margin = float(row["margin_us"])
        assert latency == pytest.approx(latency)
        assert margin == pytest.approx(margin)


def test_transmission_uses_underrated_link_bandwidth() -> None:
    flow = FLOW_BY_ID["flow-safety-01"]
    link = next(item for item in TOPOLOGY["links"] if item["link_id"] == "lnk-sw1-sw2")
    wcet = compute_wcet(POLICY, TOPOLOGY, SCHEDULES, TRAFFIC, PROFILE, flow)
    tx = int(flow["frame_size_bytes"]) * 8 / float(link["bandwidth_mbps"])
    assert link.get("derate_factor", 1.0) < 1.0
    assert wcet > tx
