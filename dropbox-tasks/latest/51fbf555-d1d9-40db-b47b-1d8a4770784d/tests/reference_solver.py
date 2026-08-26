"""Reference solver — derives expected outputs from /app/data/ and policy."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path("/app/data")
POLICY_PATH = DATA_DIR / "validation_policy.json"


@dataclass(frozen=True)
class DeadlineMiss:
    miss_id: str
    flow_id: str
    miss_type: str
    cycle: int | None
    deadline_us: int
    latency_us: float
    margin_us: float
    description: str


@dataclass(frozen=True)
class GateConflict:
    conflict_id: str
    switch_id: str
    port: str
    window_a: str
    window_b: str
    overlap_ns: int
    description: str


def load_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_policy() -> dict:
    return load_json(POLICY_PATH)  # type: ignore[return-value]


def lcm(a: int, b: int) -> int:
    return a * b // math.gcd(a, b)


def lcm_list(values: list[int]) -> int:
    result = values[0]
    for value in values[1:]:
        result = lcm(result, value)
    return result


def round_val(value: float, decimals: int) -> float:
    return round(value, decimals)


def render_template(template: str, **values: object) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def flow_enabled(flow: dict) -> bool:
    return flow.get("enabled", True) is not False


def flow_analytical_eligible(flow: dict) -> bool:
    return flow_enabled(flow) and flow.get("scheduling_exempt", False) is not True


def trace_validated(trace: dict) -> bool:
    return trace.get("validate", True) is not False


def trace_jitter_us(trace: dict) -> int:
    return int(trace.get("jitter_us", 0))


def inter_frame_gap_penalty_us(flow: dict) -> float:
    bursts = bursts_per_period(flow)
    gap = int(flow.get("inter_frame_gap_us", 0))
    if bursts <= 1:
        return 0.0
    return float(gap * (bursts - 1))


def is_switch_node(topology: dict, node_id: str) -> bool:
    for node in topology["nodes"]:
        if node["node_id"] == node_id:
            return node.get("role") == "switch"
    return False


def miss_type_rank(policy: dict, miss_type: str) -> int:
    order = policy["outputs"]["deadline_misses"]["miss_type_output_order"]
    return order.index(miss_type)


def miss_sort_key(policy: dict, miss_type: str, flow_id: str, cycle: int | None) -> tuple[int, str, int]:
    return (miss_type_rank(policy, miss_type), flow_id, cycle if cycle is not None else -1)


def miss_id_for(policy: dict, sequence: int) -> str:
    cfg = policy["outputs"]["deadline_misses"]
    return (
        f"{cfg['miss_id_prefix']}{cfg['miss_id_separator']}"
        f"{sequence:0{cfg['miss_id_sequence_width']}d}"
    )


def conflict_id_for(policy: dict, sequence: int) -> str:
    cfg = policy["outputs"]["gate_conflicts"]
    return (
        f"{cfg['conflict_id_prefix']}{cfg['conflict_id_separator']}"
        f"{sequence:0{cfg['conflict_id_sequence_width']}d}"
    )


def queue_for_class(traffic_classes: dict, class_id: str) -> int:
    for row in traffic_classes["classes"]:
        if row["class_id"] == class_id:
            return int(row["queue"])
    raise KeyError(class_id)


def deadline_shaving_us(traffic_classes: dict, class_id: str) -> int:
    for row in traffic_classes["classes"]:
        if row["class_id"] == class_id:
            return int(row.get("deadline_shaving_us", 0))
    raise KeyError(class_id)


def compliance_deadline_us(traffic_classes: dict, flow: dict) -> int:
    return int(flow["deadline_us"]) - deadline_shaving_us(traffic_classes, flow["traffic_class"])


def bandwidth_frame_bytes(flow: dict) -> int:
    return int(flow["frame_size_bytes"]) + int(flow.get("bandwidth_overhead_bytes", 0))


def bandwidth_reserved_mbps(flow: dict) -> float:
    return reserved_mbps(
        bandwidth_frame_bytes(flow),
        int(flow["period_us"]),
        bursts_per_period(flow),
    )


def queue_guard_band_us(schedule: dict, queue: int) -> float:
    bands = schedule.get("queue_guard_bands_us", {})
    return float(bands.get(str(queue), bands.get(queue, 0)))


def link_by_nodes(topology: dict, upstream: str, downstream: str) -> dict:
    for link in topology["links"]:
        if link["from"] == upstream and link["to"] == downstream:
            return link
    raise KeyError(f"{upstream}->{downstream}")


def switch_processing_us(topology: dict, node_id: str) -> float:
    return node_processing_us(topology, node_id)


def node_processing_us(topology: dict, node_id: str) -> float:
    for node in topology["nodes"]:
        if node["node_id"] == node_id:
            if node.get("role") == "grandmaster":
                return 0.0
            return float(node.get("processing_us", 0))
    return 0.0


def bursts_per_period(flow: dict) -> int:
    return int(flow.get("bursts_per_period", 1))


def reserved_mbps(frame_size: int, period_us: int, bursts: int = 1) -> float:
    return frame_size * 8 * bursts / period_us


def link_available_mbps(link: dict) -> float:
    derate = float(link.get("derate_factor", 1.0))
    return float(link["bandwidth_mbps"]) * derate


def egress_port_for_hop(topology: dict, schedules_doc: dict, upstream: str, downstream: str) -> str | None:
    link = link_by_nodes(topology, upstream, downstream)
    switch_ports = link.get("switch_ports", {})
    if upstream in switch_ports:
        return switch_ports[upstream]
    for row in schedules_doc["schedules"]:
        if row["switch_id"] == upstream:
            return row["port"]
    return None


def schedule_for_switch(schedules_doc: dict, switch_id: str, port: str) -> dict | None:
    for row in schedules_doc["schedules"]:
        if row["switch_id"] == switch_id and row["port"] == port:
            return row
    return None


def transmission_us(frame_size: int, bandwidth_mbps: float) -> float:
    return frame_size * 8 / bandwidth_mbps


def open_time_ns(schedule: dict, queue: int, gate_open: int) -> int:
    total = 0
    for interval in schedule["gate_control_list"]:
        states = interval["gate_states"]
        if states[queue] == gate_open:
            total += int(interval["interval_ns"])
    return total


def gate_wait_us(schedule: dict, queue: int, cycle_time_ns: int, gate_open: int) -> float:
    open_ns = open_time_ns(schedule, queue, gate_open)
    return (cycle_time_ns - open_ns) / 1000.0 + queue_guard_band_us(schedule, queue)


def compute_wcet(
    policy: dict,
    topology: dict,
    schedules_doc: dict,
    traffic_classes: dict,
    profile: dict,
    flow: dict,
) -> float:
    path = flow["path"]
    frame_size = int(flow["frame_size_bytes"])
    queue = queue_for_class(traffic_classes, flow["traffic_class"])
    gate_open = int(profile["gate_open_value"])
    cycle_time_ns = int(schedules_doc["cycle_time_ns"])

    total = 0.0
    for idx in range(len(path) - 1):
        link = link_by_nodes(topology, path[idx], path[idx + 1])
        total += transmission_us(frame_size, float(link["bandwidth_mbps"]))
        total += float(link["propagation_us"])

    for node in path:
        total += node_processing_us(topology, node)

    for idx in range(len(path) - 2):
        upstream = path[idx + 1]
        downstream = path[idx + 2]
        if upstream not in {n["node_id"] for n in topology["nodes"] if n.get("role") == "switch"}:
            continue
        port = egress_port_for_hop(topology, schedules_doc, upstream, downstream)
        if port is None:
            continue
        schedule = schedule_for_switch(schedules_doc, upstream, port)
        if schedule is not None:
            total += gate_wait_us(schedule, queue, cycle_time_ns, gate_open)

    total += inter_frame_gap_penalty_us(flow)

    decimals = policy["deadline_analysis"]["round_wcet_us"]
    return round_val(total, decimals)


def flows_on_link(flows: list[dict], topology: dict, link_id: str) -> list[dict]:
    link = next(item for item in topology["links"] if item["link_id"] == link_id)
    matched: list[dict] = []
    for flow in flows:
        if not flow_enabled(flow):
            continue
        path = flow["path"]
        for idx in range(len(path) - 1):
            if path[idx] == link["from"] and path[idx + 1] == link["to"]:
                matched.append(flow)
                break
    return matched


def path_skew_excess(
    flow: dict,
    offsets: dict[str, int],
    tolerance_us: int,
    grandmaster: str,
    topology: dict,
) -> int:
    total = 0
    for node in flow["path"]:
        if node == grandmaster or not is_switch_node(topology, node):
            continue
        if node in offsets:
            total += max(0, abs(offsets[node]) - tolerance_us)
    return total


def detect_gate_conflicts(policy: dict, schedules_doc: dict) -> list[GateConflict]:
    templates = policy["description_templates"]
    pending: list[tuple[str, str, str, str, int, str]] = []
    for schedule in schedules_doc["schedules"]:
        windows = schedule.get("reserved_windows", [])
        for i in range(len(windows)):
            for j in range(i + 1, len(windows)):
                a = windows[i]
                b = windows[j]
                if not a.get("exclusive") or not b.get("exclusive"):
                    continue
                start_a = int(a["start_ns"])
                end_a = start_a + int(a["duration_ns"])
                start_b = int(b["start_ns"])
                end_b = start_b + int(b["duration_ns"])
                overlap = min(end_a, end_b) - max(start_a, start_b)
                if overlap <= 0:
                    continue
                pending.append(
                    (
                        schedule["switch_id"],
                        schedule["port"],
                        a["window_id"],
                        b["window_id"],
                        overlap,
                        render_template(
                            templates["gate_conflict"],
                            window_a=a["window_id"],
                            window_b=b["window_id"],
                            overlap_ns=overlap,
                            switch_id=schedule["switch_id"],
                            port=schedule["port"],
                        ),
                    )
                )
    pending.sort(key=lambda row: (row[0], row[1], -row[4]))
    conflicts: list[GateConflict] = []
    for sequence, row in enumerate(pending, start=1):
        conflicts.append(
            GateConflict(
                conflict_id=conflict_id_for(policy, sequence),
                switch_id=row[0],
                port=row[1],
                window_a=row[2],
                window_b=row[3],
                overlap_ns=row[4],
                description=row[5],
            )
        )
    return conflicts


def detect_priority_inversions(policy: dict, traces: list[dict]) -> list[str]:
    templates = policy["description_templates"]
    grouped: dict[tuple[str, str, int], list[dict]] = {}
    for trace in traces:
        if not trace_validated(trace):
            continue
        key = (trace["egress_node"], trace["egress_port"], int(trace["cycle"]))
        grouped.setdefault(key, []).append(trace)

    inversions: list[tuple[str, str, int, int, int]] = []
    for (node, port, cycle), rows in grouped.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = rows[i]
                b = rows[j]
                if int(a["queue"]) == int(b["queue"]):
                    continue
                if int(a["queue"]) < int(b["queue"]):
                    low_prio, high_prio = a, b
                else:
                    low_prio, high_prio = b, a
                low_tx = int(low_prio["transmit_us"])
                high_tx = int(high_prio["transmit_us"])
                high_release = int(high_prio["release_us"])
                if low_tx < high_tx and high_release < low_tx:
                    inversions.append(
                        (node, port, cycle, int(low_prio["queue"]), int(high_prio["queue"]))
                    )
    inversions.sort()
    return [
        render_template(
            templates["priority_inversion"],
            lower_queue=lower_queue,
            higher_queue=higher_queue,
            egress_node=node,
            egress_port=port,
            cycle=cycle,
        )
        for node, port, cycle, lower_queue, higher_queue in inversions
    ]


def render_report(
    policy: dict,
    profile: dict,
    metrics: dict[str, float | int],
    misses: list[DeadlineMiss],
    conflicts: list[GateConflict],
    inversions: list[str],
    utilization_rows: list[dict[str, str | int | float | bool]],
) -> str:
    cfg = policy["report_markdown"]
    labels = policy["metrics"]["report_metric_labels"]
    lines = [render_template(cfg["title"], profile_name=profile["profile_name"]), ""]
    lines.append(cfg["metrics_section_heading"])
    lines.append("")
    lines.append("| " + " | ".join(cfg["metrics_table_headers"]) + " |")
    lines.append(cfg["metrics_table_separator"])
    for key, label in labels.items():
        value = metrics[key]
        if key == "priority_inversion_count":
            rendered = str(int(value))
        else:
            decimals = policy["metrics"][key]["round_decimals"]
            rendered = f"{float(value):.{decimals}f}"
        lines.append(f"| {label} | {rendered} |")

    lines.append("")
    lines.append(cfg["deadline_summary_heading"])
    lines.append("")
    for miss in misses:
        lines.append(f"- `{miss.miss_id}` [{miss.miss_type}] {miss.description}")

    lines.append("")
    lines.append(cfg["gate_conflict_heading"])
    lines.append("")
    for conflict in conflicts:
        lines.append(f"- `{conflict.conflict_id}` {conflict.description}")

    lines.append("")
    lines.append(cfg["priority_inversion_heading"])
    lines.append("")
    for description in inversions:
        lines.append(f"- {description}")

    lines.append("")
    lines.append(cfg["bandwidth_heading"])
    lines.append("")
    for row in utilization_rows:
        if cfg["bandwidth_include_overcommitted_only"] and not row["overcommitted"]:
            continue
        lines.append(
            f"- `{row['link_id']}` reserved {row['reserved_mbps']} Mbps / "
            f"{row['available_mbps']} Mbps (overcommitted: {str(row['overcommitted']).lower()})"
        )

    return "\n".join(lines) + "\n"


def enabled_flows(flows: list[dict]) -> list[dict]:
    return [flow for flow in flows if flow_enabled(flow)]


def analytical_flows(flows: list[dict]) -> list[dict]:
    return [flow for flow in flows if flow_analytical_eligible(flow)]


def hyperperiod_flows(flows: list[dict]) -> list[dict]:
    return [flow for flow in flows if flow_analytical_eligible(flow)]


def trace_raw_latency_us(trace: dict, decimals: int) -> float:
    return round_val(float(trace["arrival_us"]) - float(trace["release_us"]), decimals)


def trace_qualifies_observed(
    trace: dict,
    flow: dict,
    traffic_classes: dict,
    decimals: int,
) -> bool:
    return trace_raw_latency_us(trace, decimals) > compliance_deadline_us(traffic_classes, flow)


def trace_qualifies_clock_skew(
    trace: dict,
    flow: dict,
    traffic_classes: dict,
    offsets: dict[str, int],
    tolerance_us: int,
    grandmaster: str,
    topology: dict,
    decimals: int,
) -> bool:
    raw = trace_raw_latency_us(trace, decimals)
    skew = path_skew_excess(flow, offsets, tolerance_us, grandmaster, topology)
    adjusted = round_val(raw + skew + trace_jitter_us(trace), decimals)
    return skew > 0 and adjusted > compliance_deadline_us(traffic_classes, flow)


def validated_traces(traces: list[dict]) -> list[dict]:
    return [trace for trace in traces if trace_validated(trace)]


def egress_port_fallback_required(topology: dict, upstream: str, downstream: str) -> bool:
    link = link_by_nodes(topology, upstream, downstream)
    switch_ports = link.get("switch_ports", {})
    return upstream not in switch_ports


def compute_expected() -> tuple[
    list[DeadlineMiss],
    list[GateConflict],
    list[dict[str, str | int | float | bool]],
    dict[str, float | int],
    list[str],
    str,
]:
    policy = load_policy()
    topology = load_json(DATA_DIR / policy["inputs"]["topology"])  # type: ignore[arg-type]
    schedules_doc = load_json(DATA_DIR / policy["inputs"]["gate_schedules"])  # type: ignore[arg-type]
    traffic_classes = load_json(DATA_DIR / policy["inputs"]["traffic_classes"])  # type: ignore[arg-type]
    flows_doc = load_json(DATA_DIR / policy["inputs"]["message_flows"])  # type: ignore[arg-type]
    clock_sync = load_json(DATA_DIR / policy["inputs"]["clock_sync"])  # type: ignore[arg-type]
    traces = load_jsonl(DATA_DIR / policy["inputs"]["packet_traces"])
    profile = load_json(DATA_DIR / policy["inputs"]["tsn_profile"])  # type: ignore[arg-type]

    templates = policy["description_templates"]
    flows = flows_doc["flows"]
    eligible_flows = analytical_flows(flows)
    active_flows = enabled_flows(flows)
    flow_by_id = {flow["flow_id"]: flow for flow in flows}
    tolerance_us = int(clock_sync["tolerance_us"])
    grandmaster = clock_sync["grandmaster"]
    offsets = {row["node_id"]: int(row["offset_us"]) for row in clock_sync["offsets"]}
    latency_decimals = policy["trace_validation"]["round_latency_us"]

    misses: list[DeadlineMiss] = []
    sequence = 1

    for flow in sorted(eligible_flows, key=lambda row: row["flow_id"]):
        wcet = compute_wcet(policy, topology, schedules_doc, traffic_classes, profile, flow)
        deadline = int(flow["deadline_us"])
        compliance = compliance_deadline_us(traffic_classes, flow)
        if wcet > compliance:
            misses.append(
                DeadlineMiss(
                    miss_id=miss_id_for(policy, sequence),
                    flow_id=flow["flow_id"],
                    miss_type="analytical",
                    cycle=None,
                    deadline_us=deadline,
                    latency_us=wcet,
                    margin_us=round_val(compliance - wcet, latency_decimals),
                    description=render_template(
                        templates["analytical_miss"],
                        wcet_us=wcet,
                        deadline_us=deadline,
                        flow_id=flow["flow_id"],
                    ),
                )
            )
            sequence += 1

    for trace in validated_traces(traces):
        flow = flow_by_id[trace["flow_id"]]
        deadline = int(flow["deadline_us"])
        compliance = compliance_deadline_us(traffic_classes, flow)
        raw = trace_raw_latency_us(trace, latency_decimals)
        qualifies_observed = trace_qualifies_observed(trace, flow, traffic_classes, latency_decimals)
        qualifies_clock_skew = trace_qualifies_clock_skew(
            trace, flow, traffic_classes, offsets, tolerance_us, grandmaster, topology, latency_decimals
        )
        if qualifies_observed and not qualifies_clock_skew:
            misses.append(
                DeadlineMiss(
                    miss_id=miss_id_for(policy, sequence),
                    flow_id=flow["flow_id"],
                    miss_type="observed",
                    cycle=int(trace["cycle"]),
                    deadline_us=deadline,
                    latency_us=raw,
                    margin_us=round_val(compliance - raw, latency_decimals),
                    description=render_template(
                        templates["observed_miss"],
                        latency_us=raw,
                        deadline_us=deadline,
                        flow_id=flow["flow_id"],
                        cycle=trace["cycle"],
                    ),
                )
            )
            sequence += 1

    for trace in validated_traces(traces):
        flow = flow_by_id[trace["flow_id"]]
        deadline = int(flow["deadline_us"])
        compliance = compliance_deadline_us(traffic_classes, flow)
        raw = trace_raw_latency_us(trace, latency_decimals)
        skew = path_skew_excess(flow, offsets, tolerance_us, grandmaster, topology)
        adjusted = round_val(raw + skew + trace_jitter_us(trace), latency_decimals)
        if trace_qualifies_clock_skew(
            trace, flow, traffic_classes, offsets, tolerance_us, grandmaster, topology, latency_decimals
        ):
            misses.append(
                DeadlineMiss(
                    miss_id=miss_id_for(policy, sequence),
                    flow_id=flow["flow_id"],
                    miss_type="clock_skew",
                    cycle=int(trace["cycle"]),
                    deadline_us=deadline,
                    latency_us=adjusted,
                    margin_us=round_val(compliance - adjusted, latency_decimals),
                    description=render_template(
                        templates["clock_skew_miss"],
                        adjusted_latency_us=adjusted,
                        deadline_us=deadline,
                        flow_id=flow["flow_id"],
                        trace_id=trace["trace_id"],
                    ),
                )
            )
            sequence += 1

    misses.sort(key=lambda row: miss_sort_key(policy, row.miss_type, row.flow_id, row.cycle))

    gate_conflicts = detect_gate_conflicts(policy, schedules_doc)
    inversions = detect_priority_inversions(policy, traces)

    periods = [int(flow["period_us"]) for flow in hyperperiod_flows(flows)]
    hyperperiod = lcm_list(periods)

    utilization_rows: list[dict[str, str | int | float | bool]] = []
    reserved_decimals = policy["outputs"]["network_utilization"]["reserved_mbps_decimals"]
    ratio_decimals = policy["outputs"]["network_utilization"]["utilization_ratio_decimals"]
    for link in sorted(topology["links"], key=lambda row: row["link_id"]):
        available = link_available_mbps(link)
        reserved = 0.0
        for flow in flows_on_link(active_flows, topology, link["link_id"]):
            reserved += bandwidth_reserved_mbps(flow)
        reserved = round_val(reserved, reserved_decimals)
        ratio = round_val(reserved / available, ratio_decimals)
        utilization_rows.append(
            {
                "link_id": link["link_id"],
                "hyperperiod_us": hyperperiod,
                "reserved_mbps": reserved,
                "available_mbps": int(available),
                "utilization_ratio": ratio,
                "overcommitted": reserved > available,
            }
        )

    analytical_fail = sum(
        1
        for flow in eligible_flows
        if compute_wcet(policy, topology, schedules_doc, traffic_classes, profile, flow)
        > compliance_deadline_us(traffic_classes, flow)
    )
    validated = validated_traces(traces)
    compliant_traces = sum(
        1
        for trace in validated
        if trace_raw_latency_us(trace, latency_decimals)
        <= compliance_deadline_us(traffic_classes, flow_by_id[trace["flow_id"]])
    )
    headroom_values = [float(row["available_mbps"]) - float(row["reserved_mbps"]) for row in utilization_rows]
    sync_nodes = [row for row in clock_sync["offsets"] if row["node_id"] != grandmaster]
    compliant_nodes = sum(1 for row in sync_nodes if abs(int(row["offset_us"])) <= tolerance_us)

    metrics: dict[str, float | int] = {
        "schedule_feasibility_score": round_val(100 * (1 - analytical_fail / len(eligible_flows)), 2),
        "deadline_compliance_rate": round_val(compliant_traces / len(validated), 4),
        "bandwidth_headroom_min": round_val(min(headroom_values), 3),
        "clock_sync_compliance_rate": round_val(compliant_nodes / len(sync_nodes), 4),
        "priority_inversion_count": len(inversions),
    }

    report = render_report(policy, profile, metrics, misses, gate_conflicts, inversions, utilization_rows)
    return misses, gate_conflicts, utilization_rows, metrics, inversions, report


def format_metric(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"
