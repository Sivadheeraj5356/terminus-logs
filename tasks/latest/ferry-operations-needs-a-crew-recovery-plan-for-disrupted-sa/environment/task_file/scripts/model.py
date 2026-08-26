from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


PLAN_FILE = "ferry_recovery_plan.jsonl"
SUMMARY_FILE = "ferry_recovery_summary.json"
VALID_MODES = {"RELIEF", "SWAP", "DEADHEAD", "STANDBY"}
CLASS_RANK = {"C": 1, "B": 2, "A": 3}
STRICT_FLOORS = {
    "impact_score": 0.990,
    "coverage_score": 1.000,
    "deadline_score": 0.940,
    "crew_fit_score": 0.990,
    "rest_buffer_score": 0.960,
    "chain_score": 1.000,
    "tide_isolation_score": 0.860,
    "route_balance_score": 0.930,
    "terminal_balance_score": 1.000,
    "mode_shape_score": 0.930,
    "cell_coverage": 1.000,
}


def _json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=_json_constant)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line, parse_constant=_json_constant)
            if not isinstance(row, dict):
                raise ValueError(f"{path.name}:{line_number} is not an object")
            rows.append(row)
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_inputs(input_dir: Path) -> dict[str, Any]:
    input_dir = Path(input_dir)
    return {
        "sailings": {row["sailing_id"]: row for row in _read_jsonl(input_dir / "sailings.jsonl")},
        "crews": {row["crew_id"]: row for row in _read_jsonl(input_dir / "crews.jsonl")},
        "terminals": {row["relief_terminal_id"]: row for row in _read_jsonl(input_dir / "relief_terminals.jsonl")},
        "windows": {int(row["window"]): row for row in _read_json(input_dir / "recovery_windows.json")["windows"]},
        "capacity": _read_json(input_dir / "vessel_capacity.json")["by_window"],
        "route_targets": _read_json(input_dir / "route_targets.json")["routes"],
        "edges": _read_jsonl(input_dir / "precedence_edges.jsonl"),
        "config": _read_json(input_dir / "task_config.json"),
    }


def verify_hashes(input_dir: str | Path) -> tuple[bool, str]:
    input_dir = Path(input_dir)
    expected_path = input_dir / "input_hashes.json"
    if not expected_path.exists():
        return False, "input_hashes.json missing"
    expected = _read_json(expected_path)
    for name, want in expected.items():
        path = input_dir / name
        if not path.exists():
            return False, f"hashed input missing: {name}"
        got = _sha256(path)
        if got != want:
            return False, f"hash mismatch for {name}"
    return True, ""


def _read_outputs(output_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_dir = Path(output_dir)
    plan_path = output_dir / PLAN_FILE
    summary_path = output_dir / SUMMARY_FILE
    if not plan_path.exists():
        raise ValueError(f"{PLAN_FILE} missing")
    if not summary_path.exists():
        raise ValueError(f"{SUMMARY_FILE} missing")
    return _read_jsonl(plan_path), _read_json(summary_path)


def _impact(sailing: dict[str, Any], route_targets: dict[str, Any]) -> float:
    route_mult = float(route_targets[sailing["route_id"]]["priority_multiplier"])
    return (
        float(sailing["passengers"])
        * float(sailing["disruption_minutes"])
        * float(sailing["priority_weight"])
        * route_mult
        * (1.0 + 0.28 * float(sailing["rest_risk"]))
    )


def _hash_conflict(left: dict[str, Any], right: dict[str, Any], window: int) -> bool:
    if left["route_id"] != right["route_id"] and left["tide_group"] != right["tide_group"]:
        return False
    token = f"{left['sailing_id']}|{right['sailing_id']}|{window}|ferry-tide"
    return int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 29 == 0


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _zero(penalty: str, error: str) -> dict[str, Any]:
    return {
        "total_score": 0.0,
        "penalty": penalty,
        "error": error,
        "assigned_count": 0,
        "protected_passenger_minutes": 0.0,
        "coverage_score": 0.0,
        "impact_score": 0.0,
        "deadline_score": 0.0,
        "crew_fit_score": 0.0,
        "rest_buffer_score": 0.0,
        "chain_score": 0.0,
        "tide_isolation_score": 0.0,
        "route_balance_score": 0.0,
        "terminal_balance_score": 0.0,
        "mode_shape_score": 0.0,
        "cell_coverage": 0.0,
    }


def evaluate(input_dir: str | Path = "/app/task_file/input_data", output_dir: str | Path = "/app/task_file/output_data") -> dict[str, Any]:
    input_dir = Path(input_dir)
    ok, hash_error = verify_hashes(input_dir)
    if not ok:
        return _zero("input_integrity", hash_error)
    try:
        data = _load_inputs(input_dir)
        rows, summary = _read_outputs(output_dir)
    except Exception as exc:
        return _zero("missing_or_invalid_output", str(exc))

    sailings = data["sailings"]
    crews = data["crews"]
    terminals = data["terminals"]
    windows = data["windows"]
    capacity = data["capacity"]
    route_targets = data["route_targets"]
    config = data["config"]

    required_keys = {
        "sailing_id",
        "crew_id",
        "relief_terminal_id",
        "recovery_window",
        "priority_rank",
        "handoff_mode",
        "rest_buffer_minutes",
    }
    seen: dict[str, dict[str, Any]] = {}
    window_count: Counter[int] = Counter()
    route_count: Counter[str] = Counter()
    crew_count: Counter[str] = Counter()
    base_count: Counter[str] = Counter()
    terminal_count: Counter[str] = Counter()
    mode_count: Counter[str] = Counter()
    cell_count: Counter[tuple[int, str]] = Counter()
    terminal_window: Counter[tuple[str, int]] = Counter()
    crew_minutes: Counter[str] = Counter()
    crew_window_count: Counter[tuple[str, int]] = Counter()
    vessel_window: Counter[tuple[int, str]] = Counter()
    priority_ranks: list[int] = []
    rest_buffers: list[float] = []
    protected = 0.0
    assigned_impact = 0.0
    deadline_points = 0.0
    crew_fit_points = 0.0
    rest_points = 0.0
    errors: list[str] = []

    for index, row in enumerate(rows, start=1):
        if set(row) != required_keys:
            return _zero("schema", f"row {index} has keys {sorted(row)}")
        sid = row["sailing_id"]
        cid = row["crew_id"]
        tid = row["relief_terminal_id"]
        if sid not in sailings:
            return _zero("schema", f"unknown sailing_id {sid}")
        if sid in seen:
            return _zero("schema", f"duplicate sailing_id {sid}")
        if cid not in crews:
            return _zero("schema", f"unknown crew_id {cid}")
        if tid not in terminals:
            return _zero("schema", f"unknown relief_terminal_id {tid}")
        if row["handoff_mode"] not in VALID_MODES:
            return _zero("schema", f"invalid handoff_mode {row['handoff_mode']}")
        if not _is_int(row["recovery_window"]) or int(row["recovery_window"]) not in windows:
            return _zero("schema", "recovery_window must be an integer 1 through 6")
        if not _is_int(row["priority_rank"]):
            return _zero("schema", "priority_rank must be an integer")
        try:
            rest_buffer = float(row["rest_buffer_minutes"])
        except (TypeError, ValueError):
            return _zero("schema", "rest_buffer_minutes must be numeric")
        if not math.isfinite(rest_buffer) or rest_buffer < 10 or rest_buffer > 90:
            return _zero("schema", "rest_buffer_minutes must be finite and from 10 through 90")

        sailing = sailings[sid]
        crew = crews[cid]
        terminal = terminals[tid]
        window = int(row["recovery_window"])
        if window < int(sailing["earliest_window"]) or window > int(sailing["deadline_window"]):
            errors.append(f"{sid} outside its recovery window")
        if window not in crew["available_windows"]:
            errors.append(f"{cid} unavailable in window {window}")
        if CLASS_RANK[str(crew["certification_class"])] < CLASS_RANK[str(sailing["required_crew_class"])]:
            errors.append(f"{cid} lacks class for {sid}")
        if sailing["route_id"] not in crew["qualified_routes"]:
            errors.append(f"{cid} lacks route for {sid}")
        if sailing["vessel_class"] not in crew["vessel_classes"]:
            errors.append(f"{cid} lacks vessel class for {sid}")
        if sailing["route_id"] not in terminal["routes"]:
            errors.append(f"{tid} does not serve route for {sid}")
        if sailing["vessel_class"] not in terminal["vessel_classes"]:
            errors.append(f"{tid} cannot handle vessel class for {sid}")
        if window not in terminal["open_windows"]:
            errors.append(f"{tid} closed in window {window}")
        if crew["base_id"] not in terminal["accepted_bases"]:
            errors.append(f"{tid} does not accept base {crew['base_id']}")
        if terminal["zone_id"] not in sailing["allowed_terminal_zones"]:
            errors.append(f"{tid} zone not allowed for {sid}")

        seen[sid] = row
        priority_ranks.append(int(row["priority_rank"]))
        rest_buffers.append(rest_buffer)
        window_count[window] += 1
        route_count[str(sailing["route_id"])] += 1
        crew_count[cid] += 1
        base_count[str(crew["base_id"])] += 1
        terminal_count[tid] += 1
        mode_count[str(row["handoff_mode"])] += 1
        cell_count[(window, str(crew["base_id"]))] += 1
        terminal_window[(tid, window)] += 1
        crew_minutes[cid] += float(sailing["service_minutes"]) + rest_buffer * 0.24
        crew_window_count[(cid, window)] += 1
        vessel_window[(window, str(sailing["vessel_class"]))] += 1
        impact = _impact(sailing, route_targets)
        assigned_impact += impact
        protected += float(sailing["passengers"]) * float(sailing["disruption_minutes"])

        span = max(1, int(sailing["deadline_window"]) - int(sailing["earliest_window"]))
        deadline_points += max(0.0, 1.0 - 0.15 * ((window - int(sailing["earliest_window"])) / span))
        crew_route = float(crew["route_skill"].get(sailing["route_id"], 0.80))
        crew_vessel = float(crew["vessel_skill"].get(sailing["vessel_class"], 0.80))
        class_bonus = 0.03 * (CLASS_RANK[str(crew["certification_class"])] - CLASS_RANK[str(sailing["required_crew_class"])])
        crew_fit_points += min(1.0, 0.5 * crew_route + 0.5 * crew_vessel + class_bonus)
        target_buffer = 10.0 + 70.0 * float(sailing["rest_risk"])
        rest_points += max(0.0, 1.0 - abs(rest_buffer - target_buffer) / 80.0)

    if len(priority_ranks) != len(rows) or sorted(priority_ranks) != list(range(1, len(rows) + 1)):
        return _zero("schema", "priority_rank over assigned rows must be the permutation 1..N")
    if errors:
        return _zero("hard_constraint", errors[0])

    for sid, sailing in sailings.items():
        if bool(sailing["mandatory"]) and sid not in seen:
            return _zero("hard_constraint", f"mandatory sailing {sid} missing")
    for cid, minutes in crew_minutes.items():
        if minutes > float(crews[cid]["shift_remaining_minutes"]):
            return _zero("hard_constraint", f"crew {cid} exceeds shift minutes")
    for (cid, window), count in crew_window_count.items():
        if count > int(crews[cid]["max_sailings_per_window"]):
            return _zero("hard_constraint", f"crew {cid} has too many sailings in window {window}")
    for (tid, window), count in terminal_window.items():
        if count > int(terminals[tid]["window_capacity"]):
            return _zero("hard_constraint", f"terminal {tid} over capacity in window {window}")
    for (window, vessel), count in vessel_window.items():
        if count > int(capacity[str(window)][vessel]):
            return _zero("hard_constraint", f"vessel capacity exceeded for {vessel} in window {window}")

    total = max(1, len(rows))
    dependency_total = len(data["edges"])
    dependency_ok = 0
    for edge in data["edges"]:
        child = edge["child"]
        parent = edge["parent"]
        if child not in seen:
            dependency_ok += 1
            continue
        if parent in seen and int(seen[parent]["recovery_window"]) <= int(seen[child]["recovery_window"]):
            dependency_ok += 1

    assigned_rows = [(sid, sailings[sid], int(row["recovery_window"])) for sid, row in seen.items()]
    conflict_pairs = 0
    comparable_pairs = 0
    by_window: dict[int, list[tuple[str, dict[str, Any], int]]] = defaultdict(list)
    for item in assigned_rows:
        by_window[item[2]].append(item)
    for window, items in by_window.items():
        for left, right in combinations(items, 2):
            if left[1]["route_id"] == right[1]["route_id"] or left[1]["tide_group"] == right[1]["tide_group"]:
                comparable_pairs += 1
                if _hash_conflict(left[1], right[1], window):
                    conflict_pairs += 1

    impacts = sorted((_impact(row, route_targets) for row in sailings.values()), reverse=True)
    target_assigned = int(config["target_assigned"])
    ideal_impact = sum(impacts[:target_assigned])
    coverage_score = min(1.0, len(rows) / target_assigned)
    impact_score = min(1.0, assigned_impact / ideal_impact) if ideal_impact else 0.0
    deadline_score = deadline_points / total
    crew_fit_score = crew_fit_points / total
    rest_buffer_score = rest_points / total
    chain_score = dependency_ok / max(1, dependency_total)
    tide_isolation_score = 1.0 if comparable_pairs == 0 else max(0.0, 1.0 - conflict_pairs / max(1.0, comparable_pairs * 0.28))
    route_balance_score = 1.0
    for route, target in route_targets.items():
        observed = route_count[route] / total
        route_balance_score -= abs(observed - float(target["target_share"])) * 0.70
        if route_count[route] < int(target["min_assigned"]):
            route_balance_score -= 0.07
    route_balance_score = max(0.0, min(1.0, route_balance_score))
    terminal_balance_score = 1.0 - max(0.0, max(terminal_count.values(), default=0) / total - 0.20) * 2.0
    terminal_balance_score = max(0.0, min(1.0, terminal_balance_score))
    desired_modes = {"RELIEF": 0.34, "SWAP": 0.27, "DEADHEAD": 0.22, "STANDBY": 0.17}
    mode_shape_score = 1.0 - sum(abs(mode_count[mode] / total - share) for mode, share in desired_modes.items()) * 0.45
    mode_shape_score = max(0.0, min(1.0, mode_shape_score))
    cell_coverage = min(1.0, len(cell_count) / 24.0)
    total_score = (
        0.22 * impact_score
        + 0.10 * coverage_score
        + 0.10 * deadline_score
        + 0.12 * crew_fit_score
        + 0.08 * rest_buffer_score
        + 0.12 * chain_score
        + 0.10 * tide_isolation_score
        + 0.07 * route_balance_score
        + 0.04 * terminal_balance_score
        + 0.03 * mode_shape_score
        + 0.02 * cell_coverage
    )

    expected_summary = {
        "assigned_count": len(rows),
        "window_counts": {str(key): window_count[key] for key in sorted(window_count)},
        "route_counts": {key: route_count[key] for key in sorted(route_count)},
        "crew_counts": {key: crew_count[key] for key in sorted(crew_count)},
        "terminal_counts": {key: terminal_count[key] for key in sorted(terminal_count)},
        "total_protected_passenger_minutes": round(protected, 3),
    }
    if summary != expected_summary:
        return _zero("summary_mismatch", "ferry_recovery_summary.json does not match the plan exactly")

    return {
        "total_score": round(total_score, 6),
        "penalty": None,
        "error": None,
        "assigned_count": len(rows),
        "protected_passenger_minutes": round(protected, 3),
        "coverage_score": round(coverage_score, 6),
        "impact_score": round(impact_score, 6),
        "deadline_score": round(deadline_score, 6),
        "crew_fit_score": round(crew_fit_score, 6),
        "rest_buffer_score": round(rest_buffer_score, 6),
        "chain_score": round(chain_score, 6),
        "tide_isolation_score": round(tide_isolation_score, 6),
        "route_balance_score": round(route_balance_score, 6),
        "terminal_balance_score": round(terminal_balance_score, 6),
        "mode_shape_score": round(mode_shape_score, 6),
        "cell_coverage": round(cell_coverage, 6),
        "window_counts": dict(window_count),
        "route_counts": dict(route_count),
        "base_counts": dict(base_count),
        "mode_counts": dict(mode_count),
        "terminal_counts": dict(terminal_count),
        "rest_buffer_distinct": len({round(value) for value in rest_buffers}),
        "rest_buffer_stdev": round(_pstdev(rest_buffers), 6),
        "tide_conflict_pairs": conflict_pairs,
        "tide_comparable_pairs": comparable_pairs,
    }


def score_strict(input_dir: str | Path = "/app/task_file/input_data", output_dir: str | Path = "/app/task_file/output_data") -> dict[str, Any]:
    result = evaluate(input_dir, output_dir)
    if result.get("penalty") or result.get("error"):
        return result
    strict = float(result["total_score"]) * 0.92
    missed: dict[str, float] = {}
    for key, floor in STRICT_FLOORS.items():
        value = float(result.get(key, 0.0))
        if value < floor:
            strict *= 0.82
            missed[key] = value
    result = dict(result)
    result["missed_strict_floors"] = missed
    result["total_score_strict"] = round(strict, 6)
    return result


def _pstdev(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="include the strict wrapper score used by the verifier")
    parser.add_argument("input_dir")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    scorer = score_strict if args.strict else evaluate
    print(json.dumps(scorer(args.input_dir, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
