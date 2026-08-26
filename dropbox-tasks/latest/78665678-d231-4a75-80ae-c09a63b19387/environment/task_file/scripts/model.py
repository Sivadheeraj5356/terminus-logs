import csv
import json
from pathlib import Path

SCORE_THRESHOLD = 0.91
SCORE_NORM = 1.0


def _rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _config(path):
    cfg = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        key, value = raw.split("=", 1)
        cfg[key] = value
    return cfg


def _split(value):
    return [part for part in value.split("|") if part]


def _clamp(value):
    return max(0.0, min(1.0, value))


def evaluate(input_dir="/app/task_file/input_data", output_dir="/app/task_file/output_data"):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    try:
        samples = {row["sample_id"]: row for row in _rows(input_dir / "samples.tsv")}
        panels = {row["panel_id"]: row for row in _rows(input_dir / "panels.tsv")}
        cfg = _config(input_dir / "config.txt")
        payload = json.loads((output_dir / "batches.json").read_text(encoding="utf-8"))
        batches = payload["panels"]
        runs = payload["runs"]
    except Exception as exc:
        return {"total_score": 0.0, "error": str(exc)}

    required_families = set(_split(cfg.get("families", "")))
    sentinel_families = set(_split(cfg.get("sentinel_families", "")))
    risk_floor = int(cfg.get("risk_floor", "0"))
    risk_target = int(cfg.get("risk_target", max(risk_floor, 1)))
    min_sentinel_panels = int(cfg.get("min_sentinel_panels", "0"))
    cohort_separation = cfg.get("cohort_separation", "0") == "1"
    forbidden = []
    for pair in _split(cfg.get("forbidden_pairs", "")):
        left, right = pair.split(":", 1)
        forbidden.append((left, right))
    linked = []
    for pair in _split(cfg.get("linked_pairs", "")):
        left, right = pair.split(":", 1)
        linked.append((left, right))
    linked_pair_floor = int(cfg.get("linked_pair_floor", "0"))
    lane_count = int(cfg.get("lane_count", "0"))
    min_lane_panels = int(cfg.get("min_lane_panels", "0"))
    max_lane_panels = int(cfg.get("max_lane_panels", "999"))
    lane_setup_cap = int(cfg.get("lane_setup_cap", "999999"))
    total_setup_cap = int(cfg.get("total_setup_cap", "999999"))
    setup_target = int(cfg.get("setup_target", max(1, total_setup_cap)))
    setup_costs = {}
    for entry in _split(cfg.get("setup_costs", "")):
        left, right, cost = entry.split(":", 2)
        setup_costs[(left, right)] = int(cost)
    lane_targets = {}
    for entry in _split(cfg.get("lane_targets", "")):
        lane, family = entry.split(":", 1)
        lane_targets[lane] = family

    seen = set()
    family_seen = set()
    sentinel_panels = set()
    risk = 0
    used_a = 0
    used_b = 0
    used_panel_count = 0
    balanced_panels = 0
    panel_payloads = []
    sample_panel = {}

    for entry in batches:
        if set(entry) != {"panel_id", "sample_ids"}:
            return {"total_score": 0.0, "error": "bad schema"}
        panel_id = entry["panel_id"]
        if panel_id not in panels:
            return {"total_score": 0.0, "error": "unknown panel"}
        panel = panels[panel_id]
        ids = entry["sample_ids"]
        if not isinstance(ids, list) or len(ids) > int(panel["slot_cap"]):
            return {"total_score": 0.0, "error": "slot overflow"}

        local = set()
        local_cohorts = set()
        panel_a = 0
        panel_b = 0
        families = set(_split(panel["families"]))
        for sample_id in ids:
            if sample_id not in samples or sample_id in seen or sample_id in local:
                return {"total_score": 0.0, "error": "duplicate or unknown sample"}
            sample = samples[sample_id]
            if sample["family"] not in families:
                return {"total_score": 0.0, "error": "family mismatch"}
            if cohort_separation and sample.get("cohort", "") in local_cohorts:
                return {"total_score": 0.0, "error": "cohort collision"}
            local.add(sample_id)
            local_cohorts.add(sample.get("cohort", ""))
            panel_a += int(sample["reagent_a"])
            panel_b += int(sample["reagent_b"])
            seen.add(sample_id)
            sample_panel[sample_id] = panel_id
            family_seen.add(sample["family"])
            risk += int(sample["risk"])
            if sample["family"] in sentinel_families:
                sentinel_panels.add(panel_id)
        for left, right in forbidden:
            if left in local and right in local:
                return {"total_score": 0.0, "error": "forbidden pair colocated"}
        if panel_a > int(panel["reagent_a_cap"]) or panel_b > int(panel["reagent_b_cap"]):
            return {"total_score": 0.0, "error": "reagent overflow"}
        used_a += panel_a
        used_b += panel_b
        if ids:
            used_panel_count += 1
            load_a = panel_a / int(panel["reagent_a_cap"])
            load_b = panel_b / int(panel["reagent_b_cap"])
            if 0.25 <= load_a <= 0.95 and 0.25 <= load_b <= 0.95:
                balanced_panels += 1
        panel_payloads.append((panel_id, ids))

    scheduled = set()
    total_setup = 0
    used_lanes = 0
    lane_family_hits = {}
    if not isinstance(runs, list):
        return {"total_score": 0.0, "error": "runs must be a list"}
    for entry in runs:
        if set(entry) != {"lane", "panel_ids"}:
            return {"total_score": 0.0, "error": "bad run schema"}
        lane = entry["lane"]
        if not isinstance(lane, str) or not lane.startswith("L"):
            return {"total_score": 0.0, "error": "bad lane"}
        try:
            lane_num = int(lane[1:])
        except ValueError:
            return {"total_score": 0.0, "error": "bad lane"}
        if lane_num < 1 or lane_num > max(1, lane_count):
            return {"total_score": 0.0, "error": "lane out of range"}
        ids = entry["panel_ids"]
        if not isinstance(ids, list) or not all(isinstance(panel_id, str) for panel_id in ids):
            return {"total_score": 0.0, "error": "bad lane panels"}
        if ids:
            used_lanes += 1
            if len(ids) < min_lane_panels or len(ids) > max_lane_panels:
                return {"total_score": 0.0, "error": "lane panel count"}
        lane_setup = 0
        previous_class = None
        lane_families = set()
        for panel_id in ids:
            if panel_id not in panels or panel_id in scheduled:
                return {"total_score": 0.0, "error": "unknown or repeated scheduled panel"}
            if not any(panel_id == placed_panel and placed_ids for placed_panel, placed_ids in panel_payloads):
                return {"total_score": 0.0, "error": "scheduled empty panel"}
            current_class = panels[panel_id]["class"]
            for placed_panel, placed_ids in panel_payloads:
                if placed_panel == panel_id:
                    for sample_id in placed_ids:
                        lane_families.add(samples[sample_id]["family"])
            if previous_class is not None:
                edge = (previous_class, current_class)
                if edge not in setup_costs:
                    return {"total_score": 0.0, "error": "missing setup cost"}
                lane_setup += setup_costs[edge]
            previous_class = current_class
            scheduled.add(panel_id)
        if lane_setup > lane_setup_cap:
            return {"total_score": 0.0, "error": "lane setup overflow"}
        if ids:
            lane_family_hits[lane] = lane_families
        total_setup += lane_setup
    nonempty_panels = {panel_id for panel_id, ids in panel_payloads if ids}
    if scheduled != nonempty_panels:
        return {"total_score": 0.0, "error": "scheduled panels mismatch"}
    if lane_count and used_lanes != lane_count:
        return {"total_score": 0.0, "error": "wrong number of used lanes"}
    if total_setup > total_setup_cap:
        return {"total_score": 0.0, "error": "total setup overflow"}
    for lane, family in lane_targets.items():
        if family not in lane_family_hits.get(lane, set()):
            return {"total_score": 0.0, "error": "lane target missing"}

    mandatory = {sid for sid, row in samples.items() if row["mandatory"] == "1"}
    hard_failures = []
    if not mandatory.issubset(seen):
        hard_failures.append("missing mandatory")
    if not required_families.issubset(family_seen):
        hard_failures.append("missing family")
    if risk < risk_floor:
        hard_failures.append("risk floor")
    if len(sentinel_panels) < min_sentinel_panels:
        hard_failures.append("sentinel spread")
    linked_complete = 0
    for left, right in linked:
        left_panel = sample_panel.get(left)
        right_panel = sample_panel.get(right)
        if left_panel is None and right_panel is None:
            continue
        if left_panel is not None and left_panel == right_panel:
            linked_complete += 1
        else:
            hard_failures.append("linked pair split")
    if linked_complete < linked_pair_floor:
        hard_failures.append("linked pair floor")

    total_cap_a = sum(int(row["reagent_a_cap"]) for row in panels.values())
    total_cap_b = sum(int(row["reagent_b_cap"]) for row in panels.values())
    risk_score = min(1.0, risk / max(1, risk_target))
    family_score = len(required_families & family_seen) / max(1, len(required_families))
    load = ((used_a / max(1, total_cap_a)) + (used_b / max(1, total_cap_b))) / 2
    reagent_score = _clamp(1.0 - max(0.0, load - 0.62) * 1.8)
    coverage_score = len(seen) / max(1, len(samples))
    stewardship_score = balanced_panels / max(1, used_panel_count)
    sentinel_score = min(1.0, len(sentinel_panels) / max(1, min_sentinel_panels))
    setup_score = _clamp(1.0 - max(0.0, total_setup - setup_target) / max(1, total_setup_cap - setup_target + 1))

    if hard_failures:
        total = 0.0
    else:
        total = (
            0.30 * risk_score
            + 0.18 * family_score
            + 0.14 * reagent_score
            + 0.10 * coverage_score
            + 0.09 * stewardship_score
            + 0.09 * sentinel_score
            + 0.10 * setup_score
        )
    return {
        "total_score": round(total, 4),
        "risk_score": round(risk_score, 4),
        "family_score": round(family_score, 4),
        "reagent_score": round(reagent_score, 4),
        "coverage_score": round(coverage_score, 4),
        "stewardship_score": round(stewardship_score, 4),
        "sentinel_score": round(sentinel_score, 4),
        "setup_score": round(setup_score, 4),
        "total_setup": total_setup,
        "captured_risk": risk,
        "assigned_samples": len(seen),
        "used_panel_count": used_panel_count,
        "sentinel_panel_count": len(sentinel_panels),
        "linked_pair_count": linked_complete,
        "linked_pair_floor": linked_pair_floor,
        "lane_target_count": len(lane_targets),
        "hard_failures": hard_failures,
        "panel_count": len(panel_payloads),
    }
