import csv
import hashlib
import itertools
import math
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest


DATA_ROOT = Path(os.environ.get("EXPDESIGN_DATA_DIR", "/app/data"))
SOLUTION = Path(os.environ.get("EXPDESIGN_SOLUTION", "/app/solution.R"))
CASE_COUNT = 80
CASE_INDICES = list(range(1, CASE_COUNT + 1))

# Published table schemas used when writing deterministic hidden instances.
RUN_FIELDS = [
    "run_id",
    "trial_key",
    "case_id",
    "run_in_case",
    "elapsed_min",
    "depth_mm",
    "feed_mm_rev",
    "material_code",
    "material_label",
    "depth_level",
    "feed_level",
    "condition_family",
    "wear_mm",
    "current_dc_mean",
    "current_dc_range",
    "current_ac_rms",
    "vibration_table_rms",
    "acoustic_spindle_rms",
    "precision_weight",
]
CANDIDATE_FIELDS = ["candidate_id"] + [
    field for field in RUN_FIELDS if field != "run_id"
]
PAIR_RULE_FIELDS = ["rule_type", "left_candidate_id", "right_candidate_id"]
STRESS_SCENARIO_FIELDS = ["scenario_id", "regret_weight"]
PRECISION_RULE_FIELDS = ["scenario_id", "column", "value", "multiplier"]
DROPOUT_RULE_FIELDS = ["scenario_id", "candidate_id"]
SCALE_COLUMNS = {
    "elapsed": "elapsed_min",
    "depth": "depth_mm",
    "feed": "feed_mm_rev",
    "current_dc": "current_dc_mean",
    "vibration_table": "vibration_table_rms",
    "acoustic_spindle": "acoustic_spindle_rms",
    "wear_stage": "run_in_case",
}


# CSV helpers and deterministic row-order perturbations.
def _read_table(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_table(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _as_float(row, column):
    return float(row[column])


def _stable_order(rows, seed, key="trial_key"):
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{seed}:{row[key]}".encode("utf-8")
        ).hexdigest(),
    )


# Independent model-building and weighted L-optimal oracle.
def _load_base():
    measured = _read_table(DATA_ROOT / "measured_runs.csv")
    candidates = _read_table(DATA_ROOT / "candidate_runs.csv")
    costs = {
        row["candidate_id"]: float(row["cost"])
        for row in _read_table(DATA_ROOT / "candidate_costs.csv")
    }
    terms = [row["term"] for row in _read_table(DATA_ROOT / "model_terms.csv")]
    pool = []
    for row in measured:
        item = dict(row)
        item.pop("run_id", None)
        item["base_cost"] = _fallback_cost(item)
        pool.append(item)
    for row in candidates:
        item = dict(row)
        item.pop("candidate_id", None)
        item["base_cost"] = costs[row["candidate_id"]]
        pool.append(item)
    base_candidates = []
    for row in candidates:
        item = dict(row)
        item["base_cost"] = costs[row["candidate_id"]]
        base_candidates.append(item)
    return pool, base_candidates, terms


def _fallback_cost(row):
    cost = 6.2 + 1.35 * (int(row["material_code"]) == 2)
    cost += 0.85 * (row["depth_level"] == "deep")
    cost += 0.55 * (row["feed_level"] == "high")
    cost += 0.035 * float(row["elapsed_min"])
    cost += 0.18 * float(row["current_dc_range"])
    return round(cost, 2)


def _scale_for(measured, candidates):
    all_rows = measured + candidates
    scaling = {}
    for variable, column in SCALE_COLUMNS.items():
        values = np.asarray([_as_float(row, column) for row in all_rows], dtype=float)
        scale = float(values.std())
        scaling[variable] = (float(values.mean()), scale if scale else 1.0)
    return scaling


def _scaled(row, scaling, variable):
    center, scale = scaling[variable]
    return (_as_float(row, SCALE_COLUMNS[variable]) - center) / scale


def _design_matrix(rows, scaling, terms):
    matrix = []
    for row in rows:
        values = {
            "intercept": 1.0,
            "elapsed": _scaled(row, scaling, "elapsed"),
            "depth": _scaled(row, scaling, "depth"),
            "feed": _scaled(row, scaling, "feed"),
            "steel": 1.0 if int(row["material_code"]) == 2 else 0.0,
            "current_dc": _scaled(row, scaling, "current_dc"),
            "vibration_table": _scaled(row, scaling, "vibration_table"),
            "acoustic_spindle": _scaled(row, scaling, "acoustic_spindle"),
            "wear_stage": _scaled(row, scaling, "wear_stage"),
        }
        values["depth_feed"] = values["depth"] * values["feed"]
        values["elapsed_wear"] = values["elapsed"] * values["wear_stage"]
        values["steel_depth"] = values["steel"] * values["depth"]
        matrix.append([values[term] for term in terms])
    return np.asarray(matrix, dtype=float)


def _term_order(case_index, base_terms):
    terms = list(base_terms)
    if case_index >= 67:
        kept = [term for term in terms if term not in {"current_dc", "acoustic_spindle"}]
        if case_index >= 73:
            kept.extend(["elapsed_wear", "steel_depth"])
        if case_index % 2 == 0:
            kept = kept[:1] + kept[2:5] + kept[1:2] + kept[5:]
        return kept
    if case_index % 5 == 0:
        first = terms[:1]
        body = terms[1:]
        shift = case_index % len(body)
        return first + body[shift:] + body[:shift]
    if case_index % 7 == 0:
        return terms[:1] + list(reversed(terms[1:]))
    return terms


def _target_specs(case_index):
    slope = -0.34 - 0.02 * (case_index % 6)
    load_depth = 0.58 + 0.03 * (case_index % 4)
    acoustic = 0.22 + 0.01 * (case_index % 5)
    wear_coeffs = {
        "elapsed": 1.0,
        "wear_stage": slope,
        "acoustic_spindle": acoustic,
    }
    load_coeffs = {
        "depth": load_depth,
        "feed": 0.33,
        "depth_feed": 0.24 + 0.02 * (case_index % 4),
        "current_dc": 0.12,
    }
    if case_index >= 73:
        wear_coeffs["elapsed_wear"] = 0.16 + 0.01 * (case_index % 3)
        load_coeffs["steel_depth"] = -0.21 + 0.02 * (case_index % 4)
    specs = [
        ("wear_slope", 1.0, wear_coeffs),
        ("load_response", 0.65 + 0.04 * (case_index % 3), load_coeffs),
    ]
    if case_index % 4 != 1:
        specs.append(
            (
                "material_signal",
                0.48 + 0.03 * (case_index % 5),
                {
                    "steel": 0.52,
                    "vibration_table": -0.22 - 0.02 * (case_index % 3),
                    "acoustic_spindle": 0.27,
                },
            )
        )
    return specs


# Constraint generation and feasibility checks.
def _constraint_ok(subset, limits, quota_rules, pair_rules):
    if sum(float(row["cost"]) for row in subset) > limits["budget"] + 1e-9:
        return False
    for column, maximum_name in [
        ("case_id", "max_per_case"),
        ("condition_family", "max_per_condition_family"),
    ]:
        counts = {}
        for row in subset:
            counts[str(row[column])] = counts.get(str(row[column]), 0) + 1
        if counts and max(counts.values()) > limits[maximum_name]:
            return False
    if len({row["material_label"] for row in subset}) < limits["min_materials"]:
        return False
    if len({row["depth_level"] for row in subset}) < limits["min_depth_levels"]:
        return False
    if len({row["feed_level"] for row in subset}) < limits["min_feed_levels"]:
        return False
    for rule in quota_rules:
        count = sum(
            1 for row in subset if str(row[rule["column"]]) == str(rule["value"])
        )
        if rule["min_selected"] != "" and count < int(rule["min_selected"]):
            return False
        if rule["max_selected"] != "" and count > int(rule["max_selected"]):
            return False
    selected_ids = {row["candidate_id"] for row in subset}
    for rule in pair_rules:
        left = rule["left_candidate_id"]
        right = rule["right_candidate_id"]
        if rule["rule_type"] == "mutex":
            if left in selected_ids and right in selected_ids:
                return False
        elif rule["rule_type"] == "requires":
            if left in selected_ids and right not in selected_ids:
                return False
        else:
            raise AssertionError(f"unknown pair rule {rule['rule_type']}")
    return True


def _contrast_vectors(specs, terms):
    vectors = []
    for target_id, weight, coeffs in specs:
        vectors.append(
            (
                target_id,
                float(weight),
                np.asarray(
                    [float(coeffs.get(term, 0.0)) for term in terms], dtype=float
                ),
            )
        )
    return vectors


def _scenario_rows(subset, scenario_id, dropout_rules):
    dropped = {
        rule["candidate_id"]
        for rule in dropout_rules
        if rule["scenario_id"] == scenario_id
    }
    return [row for row in subset if row["candidate_id"] not in dropped]


def _scenario_weights(rows, scenario_id, precision_rules):
    weights = np.asarray([float(row["precision_weight"]) for row in rows], dtype=float)
    for rule in precision_rules:
        if rule["scenario_id"] != scenario_id:
            continue
        column = rule["column"]
        if any(column not in row for row in rows):
            raise AssertionError(f"unknown precision-rule column {column}")
        matches = np.asarray(
            [str(row[column]) == str(rule["value"]) for row in rows], dtype=bool
        )
        weights[matches] *= float(rule["multiplier"])
    return weights


def _criterion(
    measured,
    subset,
    scaling,
    terms,
    specs,
    rank_tolerance,
    scenario_id,
    precision_rules,
    dropout_rules,
):
    survivors = _scenario_rows(subset, scenario_id, dropout_rules)
    rows = measured + survivors
    design = _design_matrix(rows, scaling, terms)
    weights = _scenario_weights(rows, scenario_id, precision_rules)
    weighted_design = design * np.sqrt(weights)[:, None]
    singular_values = np.linalg.svd(weighted_design, compute_uv=False)
    rank = int(np.count_nonzero(singular_values > rank_tolerance))
    if rank < len(terms):
        return None, rank
    information = design.T @ (weights[:, None] * design)
    try:
        inverse = np.linalg.inv(information)
    except np.linalg.LinAlgError:
        return None, rank
    value = 0.0
    for _, weight, contrast in _contrast_vectors(specs, terms):
        value += weight * float(contrast @ inverse @ contrast)
    return value, rank


def _tie_tolerance(left, right, limits):
    return limits["tie_abs_tolerance"] + limits["tie_rel_tolerance"] * max(
        1.0, abs(left), abs(right)
    )


def _oracle(
    measured,
    candidates,
    scaling,
    terms,
    specs,
    limits,
    quota_rules,
    pair_rules,
    stress_scenarios,
    precision_rules,
    dropout_rules,
):
    records = []
    best_rank = 0
    baselines = {row["scenario_id"]: math.inf for row in stress_scenarios}
    required = limits["required_new_runs"]
    for combo in itertools.combinations(range(len(candidates)), required):
        subset = [candidates[index] for index in combo]
        if not _constraint_ok(subset, limits, quota_rules, pair_rules):
            continue
        selected = ";".join(sorted(row["candidate_id"] for row in subset))
        total_cost = sum(float(row["cost"]) for row in subset)
        values = {}
        ranks = {}
        for scenario in stress_scenarios:
            scenario_id = scenario["scenario_id"]
            value, rank = _criterion(
                measured,
                subset,
                scaling,
                terms,
                specs,
                limits["rank_tolerance"],
                scenario_id,
                precision_rules,
                dropout_rules,
            )
            values[scenario_id] = value
            ranks[scenario_id] = rank
            if value is not None:
                baselines[scenario_id] = min(baselines[scenario_id], value)
        robust_rank = min(ranks.values())
        best_rank = max(best_rank, robust_rank)
        records.append(
            {
                "selected_ids": selected,
                "total_cost": total_cost,
                "values": values,
                "rank": robust_rank,
            }
        )

    scored = []
    if records and all(math.isfinite(value) for value in baselines.values()):
        for record in records:
            if any(value is None for value in record["values"].values()):
                continue
            scenario_scores = {}
            for scenario in stress_scenarios:
                scenario_id = scenario["scenario_id"]
                scenario_scores[scenario_id] = float(scenario["regret_weight"]) * (
                    record["values"][scenario_id] / baselines[scenario_id] - 1.0
                )
            robust_value = max(scenario_scores.values())
            worst = min(
                scenario_id
                for scenario_id, score in scenario_scores.items()
                if abs(score - robust_value)
                <= _tie_tolerance(score, robust_value, limits)
            )
            scored.append(
                {
                    **record,
                    "objective_value": robust_value,
                    "worst_scenario_id": worst,
                }
            )

    if not scored:
        return {
            "status": "infeasible",
            "selected_ids": "",
            "objective_value": None,
            "rank": best_rank,
            "total_cost": None,
            "target_count": len(specs),
            "scenario_count": len(stress_scenarios),
            "worst_scenario_id": "",
        }

    minimum = min(record["objective_value"] for record in scored)
    tied = [
        record
        for record in scored
        if abs(record["objective_value"] - minimum)
        <= _tie_tolerance(record["objective_value"], minimum, limits)
    ]
    best = min(tied, key=lambda record: record["selected_ids"])
    return {
        "status": "optimal",
        "selected_ids": best["selected_ids"],
        "objective_value": best["objective_value"],
        "rank": best["rank"],
        "total_cost": best["total_cost"],
        "target_count": len(specs),
        "scenario_count": len(stress_scenarios),
        "worst_scenario_id": best["worst_scenario_id"],
    }


def _base_limits(case_index, required):
    return {
        "required_new_runs": required,
        "budget": float("inf"),
        "max_per_case": 1 if case_index % 6 in (1, 4) else 2,
        "max_per_condition_family": 2 if case_index % 8 else 3,
        "min_materials": 2,
        "min_depth_levels": 2,
        "min_feed_levels": 2,
        "rank_tolerance": 1e-9,
        "tie_abs_tolerance": 1e-10,
        "tie_rel_tolerance": 1e-8,
    }


def _quota_rules(case_index, required, candidates):
    rules = [
        {
            "column": "material_label",
            "value": "steel",
            "min_selected": 1,
            "max_selected": max(1, required - 1),
        },
        {
            "column": "depth_level",
            "value": "deep",
            "min_selected": 1,
            "max_selected": required,
        },
        {
            "column": "feed_level",
            "value": "high",
            "min_selected": 1,
            "max_selected": required,
        },
    ]
    if case_index % 9 == 0 and any(
        row["condition_family"] == "steel_shallow_low" for row in candidates
    ):
        rules.append(
            {
                "column": "condition_family",
                "value": "steel_shallow_low",
                "min_selected": "",
                "max_selected": 1,
            }
        )
    if case_index % 13 == 0 and any(
        row["material_label"] == "cast_iron" for row in candidates
    ):
        rules.append(
            {
                "column": "material_label",
                "value": "cast_iron",
                "min_selected": 1,
                "max_selected": "",
            }
        )
    return rules


def _budget_from_full_rank(
    measured,
    candidates,
    scaling,
    terms,
    specs,
    limits,
    quota_rules,
    pair_rules,
    quantile,
):
    values = []
    for combo in itertools.combinations(
        range(len(candidates)), limits["required_new_runs"]
    ):
        subset = [candidates[index] for index in combo]
        if not _constraint_ok(subset, limits, quota_rules, pair_rules):
            continue
        value, rank = _criterion(
            measured,
            subset,
            scaling,
            terms,
            specs,
            limits["rank_tolerance"],
            "nominal",
            [],
            [],
        )
        if value is not None and rank == len(terms):
            values.append(sum(float(row["cost"]) for row in subset))
    if not values:
        return None
    values.sort()
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * quantile))))
    return round(values[index] + 0.004, 2)


def _pair_rules(case_index, candidates, expected):
    if case_index < 73 or expected["status"] != "optimal":
        return []
    selected = expected["selected_ids"].split(";") if expected["selected_ids"] else []
    candidate_ids = [row["candidate_id"] for row in candidates]
    nonselected = [
        candidate_id for candidate_id in candidate_ids if candidate_id not in selected
    ]
    if case_index % 2 == 1 and len(selected) >= 2:
        return [
            {
                "rule_type": "mutex",
                "left_candidate_id": selected[0],
                "right_candidate_id": selected[1],
            }
        ]
    if case_index % 2 == 0 and selected and nonselected:
        return [
            {
                "rule_type": "requires",
                "left_candidate_id": selected[0],
                "right_candidate_id": nonselected[0],
            }
        ]
    return []


def _stress_contract(case_index, candidates, nominal_expected):
    selected_ids = (
        nominal_expected["selected_ids"].split(";")
        if nominal_expected["selected_ids"]
        else []
    )
    by_id = {row["candidate_id"]: row for row in candidates}
    selected = [by_id[candidate_id] for candidate_id in selected_ids]
    used = set()

    def choose(preferred_column, preferred_value):
        pools = [
            [
                row
                for row in selected
                if str(row[preferred_column]) == preferred_value
                and row["candidate_id"] not in used
            ],
            [row for row in selected if row["candidate_id"] not in used],
            [row for row in candidates if row["candidate_id"] not in used],
            list(candidates),
        ]
        for pool in pools:
            if pool:
                row = pool[case_index % len(pool)]
                used.add(row["candidate_id"])
                return row
        raise AssertionError("stress scenario needs at least one candidate")

    steel_dropout = choose("material_label", "steel")
    deep_dropout = choose("depth_level", "deep")
    scenarios = [
        {"scenario_id": "nominal", "regret_weight": 1.0},
        {
            "scenario_id": "steel_precision_loss",
            "regret_weight": 0.92 + 0.05 * (case_index % 5),
        },
        {
            "scenario_id": "deep_cut_instability",
            "regret_weight": 0.88 + 0.06 * (case_index % 4),
        },
    ]
    precision_rules = [
        {
            "scenario_id": "steel_precision_loss",
            "column": "material_label",
            "value": "steel",
            "multiplier": 0.26 + 0.04 * (case_index % 4),
        },
        {
            "scenario_id": "steel_precision_loss",
            "column": "feed_level",
            "value": "high",
            "multiplier": 0.62 + 0.03 * (case_index % 3),
        },
        {
            "scenario_id": "deep_cut_instability",
            "column": "depth_level",
            "value": "deep",
            "multiplier": 0.31 + 0.04 * (case_index % 5),
        },
        {
            "scenario_id": "deep_cut_instability",
            "column": "material_label",
            "value": "cast_iron",
            "multiplier": 0.70 + 0.03 * (case_index % 4),
        },
    ]
    dropout_rules = [
        {
            "scenario_id": "steel_precision_loss",
            "candidate_id": steel_dropout["candidate_id"],
        },
        {
            "scenario_id": "deep_cut_instability",
            "candidate_id": deep_dropout["candidate_id"],
        },
    ]

    if case_index >= 41:
        sensor_dropout = choose("feed_level", "low")
        scenarios.append(
            {
                "scenario_id": "compound_sensor_shift",
                "regret_weight": 0.84 + 0.05 * (case_index % 6),
            }
        )
        precision_rules.extend(
            [
                {
                    "scenario_id": "compound_sensor_shift",
                    "column": "condition_family",
                    "value": sensor_dropout["condition_family"],
                    "multiplier": 0.23 + 0.03 * (case_index % 4),
                },
                {
                    "scenario_id": "compound_sensor_shift",
                    "column": "feed_level",
                    "value": "low",
                    "multiplier": 0.55 + 0.04 * (case_index % 3),
                },
            ]
        )
        dropout_rules.append(
            {
                "scenario_id": "compound_sensor_shift",
                "candidate_id": sensor_dropout["candidate_id"],
            }
        )

    if case_index % 19 == 0:
        scenarios.append({"scenario_id": "plant_shutdown", "regret_weight": 1.2})
        dropout_rules.extend(
            {
                "scenario_id": "plant_shutdown",
                "candidate_id": row["candidate_id"],
            }
            for row in candidates
        )
    return scenarios, precision_rules, dropout_rules


# Hidden fixture generation. Case indices select scenario families such as
# infeasible budgets, one-sided quotas, term variants, and pair constraints.
def _renumber_measured(rows, case_index):
    measured = []
    for index, row in enumerate(rows, start=1):
        item = dict(row)
        item.pop("candidate_id", None)
        item.pop("base_cost", None)
        item["run_id"] = f"R{case_index:03d}_{index:02d}"
        measured.append(item)
    return measured


def _renumber_candidates(rows, case_index):
    candidates = []
    for index, row in enumerate(rows, start=1):
        item = dict(row)
        base_cost = float(item.pop("base_cost"))
        item.pop("run_id", None)
        item["candidate_id"] = f"D{case_index:03d}_{index:02d}"
        token = int(
            hashlib.sha256(
                f"{case_index}:{item['trial_key']}:cost".encode("utf-8")
            ).hexdigest()[:4],
            16,
        )
        multiplier = 1.0 + ((token % 11) - 5) * 0.012
        item["cost"] = round(base_cost * multiplier + 0.015 * (case_index % 7), 2)
        weight_shift = 1.0 + ((token % 7) - 3) * 0.01
        item["precision_weight"] = (
            f"{float(item['precision_weight']) * weight_shift:.8f}"
        )
        candidates.append(item)
    return candidates


def _make_instance(case_index):
    pool, base_candidates, base_terms = _load_base()
    measured_count = 7 + (case_index % 3)
    keep = 8 + (case_index % 4)
    required = [3, 4, 4, 5][case_index % 4]
    seed = 7207 + 1543 * case_index
    measured_rows = _stable_order([dict(row) for row in pool], seed)[:measured_count]
    measured_keys = {row["trial_key"] for row in measured_rows}
    ordered_candidates = [
        dict(row)
        for row in _stable_order(base_candidates, seed + 37)
        if row["trial_key"] not in measured_keys
    ]
    terms = _term_order(case_index, base_terms)
    specs = _target_specs(case_index)
    for attempt in range(8):
        candidates = _renumber_candidates(
            ordered_candidates[: keep + attempt], case_index
        )
        measured = _renumber_measured(measured_rows, case_index)
        scaling = _scale_for(measured, candidates)
        limits = _base_limits(case_index, min(required, len(candidates)))
        quota_rules = _quota_rules(case_index, limits["required_new_runs"], candidates)
        nominal_scenarios = [{"scenario_id": "nominal", "regret_weight": 1.0}]
        if case_index % 17 == 0:
            limits["min_materials"] = 3
            limits["budget"] = 10**9
            stress = _stress_contract(
                case_index, candidates, {"selected_ids": ""}
            )
            return (
                measured,
                candidates,
                scaling,
                terms,
                specs,
                limits,
                quota_rules,
                [],
                *stress,
            )
        if case_index % 11 == 0:
            cheapest = sorted(float(row["cost"]) for row in candidates)
            cutoff = sum(cheapest[: limits["required_new_runs"]]) - 0.01
            limits["budget"] = round(max(0.0, cutoff), 2)
            stress = _stress_contract(
                case_index, candidates, {"selected_ids": ""}
            )
            return (
                measured,
                candidates,
                scaling,
                terms,
                specs,
                limits,
                quota_rules,
                [],
                *stress,
            )
        quantile = 0.28 + 0.07 * (case_index % 6)
        budget = _budget_from_full_rank(
            measured,
            candidates,
            scaling,
            terms,
            specs,
            limits,
            quota_rules,
            [],
            quantile,
        )
        if budget is not None:
            limits["budget"] = budget
            base_expected = _oracle(
                measured,
                candidates,
                scaling,
                terms,
                specs,
                limits,
                quota_rules,
                [],
                nominal_scenarios,
                [],
                [],
            )
            pair_rules = _pair_rules(case_index, candidates, base_expected)
            nominal_expected = _oracle(
                measured,
                candidates,
                scaling,
                terms,
                specs,
                limits,
                quota_rules,
                pair_rules,
                nominal_scenarios,
                [],
                [],
            )
            stress_scenarios, precision_rules, dropout_rules = _stress_contract(
                case_index, candidates, nominal_expected
            )
            expected = _oracle(
                measured,
                candidates,
                scaling,
                terms,
                specs,
                limits,
                quota_rules,
                pair_rules,
                stress_scenarios,
                precision_rules,
                dropout_rules,
            )
            expected_status = "infeasible" if case_index % 19 == 0 else "optimal"
            if expected["status"] == expected_status:
                return (
                    measured,
                    candidates,
                    scaling,
                    terms,
                    specs,
                    limits,
                    quota_rules,
                    pair_rules,
                    stress_scenarios,
                    precision_rules,
                    dropout_rules,
                )
    raise AssertionError(f"could not construct scenario {case_index}")


def _write_instance(root, case_index):
    (
        measured,
        candidates,
        scaling,
        terms,
        specs,
        limits,
        quota_rules,
        pair_rules,
        stress_scenarios,
        precision_rules,
        dropout_rules,
    ) = _make_instance(case_index)
    expected = _oracle(
        measured,
        candidates,
        scaling,
        terms,
        specs,
        limits,
        quota_rules,
        pair_rules,
        stress_scenarios,
        precision_rules,
        dropout_rules,
    )
    _write_table(root / "measured_runs.csv", measured, RUN_FIELDS)
    _write_table(root / "candidate_runs.csv", candidates, CANDIDATE_FIELDS)
    _write_table(
        root / "candidate_costs.csv",
        [
            {"candidate_id": row["candidate_id"], "cost": f"{float(row['cost']):.2f}"}
            for row in candidates
        ],
        ["candidate_id", "cost"],
    )
    _write_table(root / "design_limits.csv", [limits], list(limits))
    _write_table(
        root / "quota_rules.csv",
        quota_rules,
        ["column", "value", "min_selected", "max_selected"],
    )
    _write_table(root / "pair_rules.csv", pair_rules, PAIR_RULE_FIELDS)
    _write_table(
        root / "stress_scenarios.csv", stress_scenarios, STRESS_SCENARIO_FIELDS
    )
    _write_table(root / "precision_rules.csv", precision_rules, PRECISION_RULE_FIELDS)
    _write_table(root / "dropout_rules.csv", dropout_rules, DROPOUT_RULE_FIELDS)
    _write_table(
        root / "scaling.csv",
        [
            {"variable": variable, "center": center, "scale": scale}
            for variable, (center, scale) in scaling.items()
        ],
        ["variable", "center", "scale"],
    )
    _write_table(root / "model_terms.csv", [{"term": term} for term in terms], ["term"])
    contrast_rows = []
    weight_rows = []
    for target_id, weight, coeffs in specs:
        weight_rows.append({"target_id": target_id, "target_weight": weight})
        for term, coefficient in coeffs.items():
            if term not in terms:
                continue
            contrast_rows.append(
                {"target_id": target_id, "term": term, "coefficient": coefficient}
            )
    _write_table(
        root / "target_contrasts.csv",
        contrast_rows,
        ["target_id", "term", "coefficient"],
    )
    _write_table(
        root / "target_weights.csv", weight_rows, ["target_id", "target_weight"]
    )
    return expected


# Candidate execution and output contract assertions.
def _parse_answer(path):
    rows = _read_table(path)
    assert len(rows) == 1, "output must contain exactly one row"
    row = rows[0]
    for column in [
        "status",
        "selected_ids",
        "objective_value",
        "rank",
        "total_cost",
        "target_count",
        "scenario_count",
        "worst_scenario_id",
    ]:
        assert column in row, f"missing output column {column}"
    return row


def _run_candidate(input_dir, output_path):
    assert SOLUTION.is_file(), "/app/solution.R must exist"
    completed = subprocess.run(
        ["Rscript", str(SOLUTION), str(input_dir), str(output_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _na_text(value):
    return str(value).strip().upper() in {"NA", "NAN"}


def _assert_answer(observed, expected):
    assert observed["status"] == expected["status"]
    assert observed["selected_ids"] == expected["selected_ids"]
    assert int(float(observed["rank"])) == int(expected["rank"])
    assert int(float(observed["target_count"])) == int(expected["target_count"])
    assert int(float(observed["scenario_count"])) == int(expected["scenario_count"])
    assert observed["worst_scenario_id"] == expected["worst_scenario_id"]
    if expected["status"] == "infeasible":
        assert _na_text(observed["objective_value"])
        assert _na_text(observed["total_cost"])
        return
    observed_value = float(observed["objective_value"])
    expected_value = float(expected["objective_value"])
    observed_cost = float(observed["total_cost"])
    expected_cost = float(expected["total_cost"])
    assert math.isclose(observed_value, expected_value, rel_tol=2e-6, abs_tol=2e-7)
    assert math.isclose(observed_cost, expected_cost, rel_tol=1e-9, abs_tol=1e-6)


# Pytest collection: one parameterized test, 80 semantic cases, descriptive IDs.
def _scenario_tags(case_index):
    """Name the main contract features stressed by a generated case."""
    tags = []
    if case_index % 11 == 0:
        tags.append("budget_infeasible")
    if case_index % 17 == 0:
        tags.append("material_infeasible")
    if case_index % 9 == 0:
        tags.append("max_only_quota")
    if case_index % 13 == 0:
        tags.append("min_only_quota")
    if case_index % 5 == 0 or case_index % 7 == 0:
        tags.append("term_reorder")
    if case_index >= 67:
        tags.append("omitted_terms")
    if case_index >= 73 and case_index % 11 != 0 and case_index % 17 != 0:
        tags.append("pair_mutex" if case_index % 2 == 1 else "pair_requires")
    scenario_count = (4 if case_index >= 41 else 3) + (case_index % 19 == 0)
    count_name = {3: "three", 4: "four", 5: "five"}[scenario_count]
    tags.append(f"{count_name}_stress_scenarios")
    if case_index % 19 == 0:
        tags.append("stress_infeasible")
    if case_index % 4 == 1:
        tags.append("two_targets")
    return tags or ["nominal"]


def _case_id(case_index):
    return f"wear_{case_index:03d}__{'__'.join(_scenario_tags(case_index))}"


@pytest.mark.parametrize("case_index", CASE_INDICES, ids=_case_id)
def test_machining_wear_design_scenario(case_index, tmp_path):
    """Robust scenarios cover minimax regret, dropouts, precision shifts, and constraints."""
    input_dir = tmp_path / "input"
    output_path = tmp_path / "answer.csv"
    expected = _write_instance(input_dir, case_index)
    _run_candidate(input_dir, output_path)
    observed = _parse_answer(output_path)
    _assert_answer(observed, expected)
