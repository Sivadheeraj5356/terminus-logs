"""Independent behavioral verification for robust path-budget evaluation."""

import csv
import math
import shutil
import subprocess
from itertools import product
from pathlib import Path

import pytest
from scipy.optimize import linprog


TRANSIENT = [f"s{i}" for i in range(4)]
STATES = TRANSIENT + ["goal", "fail"]
ACTIONS = range(3)
OUTPUT_FIELDS = [
    "case_id",
    "unsupported",
    "low_count_pairs",
    "robust_reachability",
    "nominal_reachability",
    "robust_gap",
    "initial_expected_ambiguity_units",
    "initial_expected_budget_cost",
    "initial_expected_intervention",
    "transport_monotonicity_residual",
    "intervention_monotonicity_residual",
]
FLOAT_FIELDS = set(OUTPUT_FIELDS[3:])
TASK_TOKEN = "path_budgeted_transition_robust_reachability"
SURFACES = {
    "public": Path("/app/data"),
    "hidden": Path("/tests/fixtures/hidden"),
}


def table(root, name):
    """Read one CSV relation by header."""
    with (root / name).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_table(path, records, fieldnames=None):
    """Write a deterministic relation used by a verifier-owned mutation."""
    if fieldnames is None:
        fieldnames = list(records[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def integer(value):
    """Return whether a numeric value is finite and integral."""
    return math.isfinite(value) and value == math.floor(value)


def l1_minimum(probabilities, values, radius):
    """Compute the simplex L1 minimum by ordered mass transport."""
    remaining = min(max(radius, 0.0), 2.0) / 2
    sources = [
        [values[i], i, probabilities[i]]
        for i in range(len(values))
        if probabilities[i] > 1e-15
    ]
    sinks = [
        [values[i], i, 1 - probabilities[i]]
        for i in range(len(values))
        if probabilities[i] < 1 - 1e-15
    ]
    sources.sort(key=lambda item: (-item[0], item[1]))
    sinks.sort(key=lambda item: (item[0], item[1]))
    answer = sum(p * x for p, x in zip(probabilities, values, strict=True))
    high = low = 0
    while remaining > 1e-15 and high < len(sources) and low < len(sinks):
        if sources[high][0] <= sinks[low][0] + 1e-15:
            break
        if sources[high][1] == sinks[low][1]:
            low += 1
            continue
        moved = min(remaining, sources[high][2], sinks[low][2])
        answer -= moved * (sources[high][0] - sinks[low][0])
        remaining -= moved
        sources[high][2] -= moved
        sinks[low][2] -= moved
        if sources[high][2] <= 1e-15:
            high += 1
        if sinks[low][2] <= 1e-15:
            low += 1
    return answer


def l1_linear_program(probabilities, values, radius):
    """Solve the same transport problem through an independent generic LP."""
    n = len(probabilities)
    objective = list(values) + [0.0] * n
    inequalities = []
    bounds = [(0.0, 1.0)] * n + [(0.0, None)] * n
    for index in range(n):
        positive = [0.0] * (2 * n)
        positive[index] = 1.0
        positive[n + index] = -1.0
        inequalities.append((positive, probabilities[index]))
        negative = [0.0] * (2 * n)
        negative[index] = -1.0
        negative[n + index] = -1.0
        inequalities.append((negative, -probabilities[index]))
    inequalities.append(
        ([0.0] * n + [1.0] * n, min(max(radius, 0.0), 2.0))
    )
    result = linprog(
        objective,
        A_ub=[row for row, _ in inequalities],
        b_ub=[rhs for _, rhs in inequalities],
        A_eq=[[1.0] * n + [0.0] * n],
        b_eq=[1.0],
        bounds=bounds,
        method="highs",
    )
    assert result.success, result.message
    return float(result.fun)


def oracle(root):
    """Recompute every requested result from verifier-owned relations."""
    count_rows = table(root, "nominal_transition_counts.csv")
    kernels = {}
    totals = {}
    malformed_counts = False
    for state in TRANSIENT:
        for action in ACTIONS:
            part = [
                row
                for row in count_rows
                if row["state"] == state and int(row["action"]) == action
            ]
            try:
                values = [float(row["count"]) for row in part]
            except ValueError:
                values = [math.nan]
            valid = (
                bool(part)
                and all(math.isfinite(value) and value >= 0 for value in values)
                and all(row["destination"] in STATES for row in part)
            )
            malformed_counts = malformed_counts or not valid
            total = sum(values) if all(math.isfinite(value) for value in values) else 0.0
            totals[(state, action)] = total
            probabilities = [0.0] * len(STATES)
            if total > 0 and valid:
                for row, value in zip(part, values, strict=True):
                    probabilities[STATES.index(row["destination"])] += value / total
            kernels[(state, action)] = probabilities

    policy_rows = table(root, "target_policies.csv")
    profile_rows = table(root, "ambiguity_profiles.csv")
    answers = {}

    for case in table(root, "robust_budget_cases.csv"):
        try:
            horizon = float(case["horizon"])
            transport_budget = float(case["budget_units"])
            intervention_budget = float(case["intervention_budget_units"])
            radius = float(case["l1_radius_per_unit"])
            minimum_count = float(case["minimum_pair_count"])
        except (KeyError, ValueError):
            horizon = transport_budget = intervention_budget = radius = math.nan
            minimum_count = math.nan

        low = (
            sum(total < minimum_count for total in totals.values())
            if math.isfinite(minimum_count)
            else 12
        )
        invalid = (
            malformed_counts
            or any(total <= 0 for total in totals.values())
            or not integer(horizon)
            or horizon < 1
            or not integer(transport_budget)
            or transport_budget < 0
            or not integer(intervention_budget)
            or intervention_budget < 0
            or not math.isfinite(radius)
            or radius < 0
            or not math.isfinite(minimum_count)
            or minimum_count < 0
            or case.get("start_state") not in TRANSIENT
            or low > 0
        )

        policy = {}
        for state in TRANSIENT:
            part = [
                row
                for row in policy_rows
                if row["policy_id"] == case.get("policy_id")
                and row["state"] == state
            ]
            try:
                actions = [int(row["action"]) for row in part]
                probabilities = [float(row["probability"]) for row in part]
            except ValueError:
                actions = []
                probabilities = []
            valid = (
                len(part) == 3
                and sorted(actions) == list(ACTIONS)
                and len(set(actions)) == 3
                and all(math.isfinite(value) and value > 0 for value in probabilities)
                and abs(sum(probabilities) - 1) <= 1e-12
            )
            invalid = invalid or not valid
            policy[state] = (
                {action: probability for action, probability in zip(actions, probabilities)}
                if valid
                else {}
            )

        profile = {}
        for state in TRANSIENT:
            for action in ACTIONS:
                part = [
                    row
                    for row in profile_rows
                    if row["ambiguity_profile_id"]
                    == case.get("ambiguity_profile_id")
                    and row["state"] == state
                    and int(row["action"]) == action
                ]
                try:
                    cost = float(part[0]["budget_cost"])
                    multiplier = float(part[0]["radius_multiplier"])
                    cap = float(part[0]["max_ambiguity_units"])
                except (IndexError, KeyError, ValueError):
                    cost = multiplier = cap = math.nan
                valid = (
                    len(part) == 1
                    and integer(cost)
                    and cost > 0
                    and math.isfinite(multiplier)
                    and multiplier > 0
                    and integer(cap)
                    and cap >= 0
                )
                invalid = invalid or not valid
                profile[(state, action)] = (
                    (int(cost), multiplier, int(cap)) if valid else (1, 1.0, 0)
                )

        unsupported = invalid
        if not unsupported:
            horizon = int(horizon)
            transport_budget = int(transport_budget)
            intervention_budget = int(intervention_budget)
            values = [
                [
                    [
                        [0.0] * (intervention_budget + 1)
                        for _ in range(transport_budget + 1)
                    ]
                    for _ in STATES
                ]
                for _ in range(horizon + 1)
            ]
            nominal = [[0.0] * len(STATES) for _ in range(horizon + 1)]
            for h in range(horizon + 1):
                nominal[h][4] = 1.0
                for budget in range(transport_budget + 1):
                    for interventions in range(intervention_budget + 1):
                        values[h][4][budget][interventions] = 1.0

            transport_residual = 0.0
            intervention_residual = 0.0
            for h in range(1, horizon + 1):
                for state_index, state in enumerate(TRANSIENT):
                    nominal[h][state_index] = sum(
                        policy[state][action]
                        * sum(
                            kernels[(state, action)][destination]
                            * nominal[h - 1][destination]
                            for destination in range(len(STATES))
                        )
                        for action in ACTIONS
                    )
                    for budget in range(transport_budget + 1):
                        for interventions in range(intervention_budget + 1):
                            ranges = [
                                range(min(profile[(state, action)][2], budget // profile[(state, action)][0]) + 1)
                                for action in ACTIONS
                            ]
                            candidates = []
                            for plan in product(*ranges):
                                total_cost = sum(
                                    plan[action] * profile[(state, action)][0]
                                    for action in ACTIONS
                                )
                                active = sum(units > 0 for units in plan)
                                if total_cost > budget or active > interventions:
                                    continue
                                child = [
                                    values[h - 1][destination][budget - total_cost][interventions - active]
                                    for destination in range(len(STATES))
                                ]
                                plan_value = sum(
                                    policy[state][action]
                                    * l1_minimum(
                                        kernels[(state, action)],
                                        child,
                                        plan[action] * radius * profile[(state, action)][1],
                                    )
                                    for action in ACTIONS
                                )
                                candidates.append((plan_value, plan))
                            best = min(value for value, _ in candidates)
                            chosen_value, _ = next(
                                item for item in candidates if item[0] <= best + 1e-12
                            )
                            values[h][state_index][budget][interventions] = chosen_value
                    for budget in range(transport_budget):
                        for interventions in range(intervention_budget + 1):
                            transport_residual = max(
                                transport_residual,
                                values[h][state_index][budget + 1][interventions]
                                - values[h][state_index][budget][interventions],
                                0.0,
                            )
                    for budget in range(transport_budget + 1):
                        for interventions in range(intervention_budget):
                            intervention_residual = max(
                                intervention_residual,
                                values[h][state_index][budget][interventions + 1]
                                - values[h][state_index][budget][interventions],
                                0.0,
                            )

            start = TRANSIENT.index(case["start_state"])
            robust = values[horizon][start][transport_budget][intervention_budget]
            nominal_value = nominal[horizon][start]
            start_state = case["start_state"]
            ranges = [
                range(min(profile[(start_state, action)][2], transport_budget // profile[(start_state, action)][0]) + 1)
                for action in ACTIONS
            ]
            candidates = []
            for plan in product(*ranges):
                total_cost = sum(
                    plan[action] * profile[(start_state, action)][0]
                    for action in ACTIONS
                )
                active = sum(units > 0 for units in plan)
                if total_cost > transport_budget or active > intervention_budget:
                    continue
                child = [
                    values[horizon - 1][destination][transport_budget - total_cost][intervention_budget - active]
                    for destination in range(len(STATES))
                ]
                plan_value = sum(
                    policy[start_state][action]
                    * l1_minimum(
                        kernels[(start_state, action)],
                        child,
                        plan[action] * radius * profile[(start_state, action)][1],
                    )
                    for action in ACTIONS
                )
                candidates.append((plan_value, plan, total_cost, active))
            best = min(value for value, _, _, _ in candidates)
            _, chosen_plan, expected_cost, expected_active = next(
                item for item in candidates if item[0] <= best + 1e-12
            )
            expected_units = sum(
                policy[start_state][action] * chosen_plan[action]
                for action in ACTIONS
            )
            gap = nominal_value - robust
            diagnostics = (
                robust,
                nominal_value,
                gap,
                expected_units,
                expected_cost,
                expected_active,
                transport_residual,
                intervention_residual,
            )
            unsupported = not all(math.isfinite(value) for value in diagnostics)

        result = {
            "case_id": case["case_id"],
            "unsupported": int(unsupported),
            "low_count_pairs": int(low),
        }
        if unsupported:
            result.update({field: None for field in OUTPUT_FIELDS[3:]})
        else:
            result.update(
                robust_reachability=robust,
                nominal_reachability=nominal_value,
                robust_gap=gap,
                initial_expected_ambiguity_units=expected_units,
                initial_expected_budget_cost=expected_cost,
                initial_expected_intervention=expected_active,
                transport_monotonicity_residual=transport_residual,
                intervention_monotonicity_residual=intervention_residual,
            )
        answers[case["case_id"]] = result
    return answers


EXPECTED = {name: oracle(path) for name, path in SURFACES.items()}
OBSERVED = {}


def execute(name, root):
    """Run the candidate against one isolated relational data surface."""
    output = Path(f"/tmp/{TASK_TOKEN}-{name}.csv")
    output.unlink(missing_ok=True)
    completed = subprocess.run(
        ["Rscript", "/app/estimate.R", str(root), str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.is_file() and output.stat().st_size > 0
    with output.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    return fields, rows, {row["case_id"]: row for row in rows}


def observed(name):
    """Cache one candidate execution while preserving its failure."""
    if name not in OBSERVED:
        try:
            OBSERVED[name] = ("ok", execute(name, SURFACES[name]))
        except Exception as error:
            OBSERVED[name] = ("error", error)
    status, payload = OBSERVED[name]
    if status == "error":
        raise payload
    return payload


def assert_result(actual, expected):
    """Compare one candidate row with independently computed fields."""
    assert list(actual) == OUTPUT_FIELDS
    for field, wanted in expected.items():
        value = actual[field]
        if wanted is None:
            assert value == ""
        elif field in {"unsupported", "low_count_pairs"}:
            try:
                parsed = int(value)
            except ValueError:
                pytest.fail(f"{field} must use integer encoding, got {value!r}")
            assert parsed == wanted
        elif field in FLOAT_FIELDS:
            parsed = float(value)
            assert math.isfinite(parsed)
            assert parsed == pytest.approx(wanted, abs=1e-8, rel=1e-10)
        else:
            assert value == wanted


def assert_surface(root, execution_name):
    """Run and fully compare one verifier-owned surface."""
    expected = oracle(root)
    fields, rows, indexed = execute(execution_name, root)
    assert fields == OUTPUT_FIELDS
    assert [row["case_id"] for row in rows] == sorted(expected)
    assert len(rows) == len(expected)
    for case_id, wanted in expected.items():
        assert_result(indexed[case_id], wanted)
    return rows, indexed, expected


@pytest.mark.parametrize(
    ("surface", "case_id"),
    [
        (surface, case_id)
        for surface in SURFACES
        for case_id in sorted(EXPECTED[surface])
    ],
)
def test_semantic_case(surface, case_id):
    """Every public and hidden case must match the independent Bellman oracle."""
    fields, rows, indexed = observed(surface)
    assert fields == OUTPUT_FIELDS
    assert [row["case_id"] for row in rows] == sorted(EXPECTED[surface])
    assert len(rows) == len(EXPECTED[surface])
    assert_result(indexed[case_id], EXPECTED[surface][case_id])


@pytest.mark.parametrize("index", range(48))
def test_l1_transport_against_linear_program(index):
    """The transport primitive is checked against an independent LP family."""
    rows = table(SURFACES["hidden"], "nominal_transition_counts.csv")
    state = TRANSIENT[(index // 3) % len(TRANSIENT)]
    action = index % 3
    part = [
        row
        for row in rows
        if row["state"] == state and int(row["action"]) == action
    ]
    total = sum(float(row["count"]) for row in part)
    probabilities = [0.0] * len(STATES)
    for row in part:
        probabilities[STATES.index(row["destination"])] += float(row["count"]) / total
    values = [
        0.48 + 0.43 * math.sin((index + 2) * (destination + 3))
        for destination in range(4)
    ] + [1.0, 0.0]
    radius = (index % 11) * 0.19
    assert l1_minimum(probabilities, values, radius) == pytest.approx(
        l1_linear_program(probabilities, values, radius),
        abs=2e-10,
        rel=1e-10,
    )


def copy_surface(source, destination):
    """Copy all relational inputs to an isolated mutation directory."""
    for path in source.glob("*.csv"):
        shutil.copy2(path, destination / path.name)


def test_row_and_header_order_invariance(tmp_path):
    """All relations remain keyed when rows and columns are independently permuted."""
    for path in SURFACES["hidden"].glob("*.csv"):
        records = table(SURFACES["hidden"], path.name)
        fields = list(records[0])
        rotated = fields[2:] + fields[:2]
        write_table(tmp_path / path.name, list(reversed(records)), rotated)
    assert_surface(tmp_path, "permuted")


def test_count_scale_equivariance(tmp_path):
    """Scaling fitted counts and thresholds together preserves every result."""
    copy_surface(SURFACES["hidden"], tmp_path)
    counts = table(tmp_path, "nominal_transition_counts.csv")
    for row in counts:
        row["count"] = str(float(row["count"]) * 7)
    write_table(tmp_path / "nominal_transition_counts.csv", counts)
    cases = table(tmp_path, "robust_budget_cases.csv")
    for row in cases:
        row["minimum_pair_count"] = str(float(row["minimum_pair_count"]) * 7)
    write_table(tmp_path / "robust_budget_cases.csv", cases)
    _, scaled, expected = assert_surface(tmp_path, "count-scaled")
    baseline = observed("hidden")[2]
    for case_id, row in scaled.items():
        for field in OUTPUT_FIELDS:
            if field in FLOAT_FIELDS and row[field] != "":
                assert float(row[field]) == pytest.approx(
                    float(baseline[case_id][field]), abs=1e-8, rel=1e-10
                )
            else:
                assert row[field] == baseline[case_id][field]
        assert expected[case_id]["unsupported"] == EXPECTED["hidden"][case_id]["unsupported"]


def subset_cases(root, count=12):
    """Retain a deterministic cross-section for counterfactual executions."""
    rows = table(root, "robust_budget_cases.csv")
    chosen = [row for index, row in enumerate(rows) if index % 5 == 0][:count]
    write_table(root / "robust_budget_cases.csv", chosen)


def test_zero_radius_collapse(tmp_path):
    """Zero radius collapses robust values and all initial ambiguity use."""
    copy_surface(SURFACES["hidden"], tmp_path)
    subset_cases(tmp_path)
    cases = table(tmp_path, "robust_budget_cases.csv")
    for row in cases:
        row["l1_radius_per_unit"] = "0"
    write_table(tmp_path / "robust_budget_cases.csv", cases)
    _, indexed, expected = assert_surface(tmp_path, "zero-radius")
    supported = 0
    for case_id, wanted in expected.items():
        if wanted["unsupported"]:
            continue
        supported += 1
        row = indexed[case_id]
        assert float(row["robust_reachability"]) == pytest.approx(
            float(row["nominal_reachability"]), abs=1e-10
        )
        assert abs(float(row["robust_gap"])) <= 1e-10
        assert abs(float(row["initial_expected_ambiguity_units"])) <= 1e-10
        assert abs(float(row["initial_expected_budget_cost"])) <= 1e-10
        assert abs(float(row["initial_expected_intervention"])) <= 1e-10
    assert supported > 0


def test_profile_caps_are_load_bearing(tmp_path):
    """A zero-cap profile disables ambiguity even when both budgets are positive."""
    copy_surface(SURFACES["hidden"], tmp_path)
    subset_cases(tmp_path)
    profiles = table(tmp_path, "ambiguity_profiles.csv")
    for row in profiles:
        row["max_ambiguity_units"] = "0"
    write_table(tmp_path / "ambiguity_profiles.csv", profiles)
    _, indexed, expected = assert_surface(tmp_path, "zero-cap")
    supported = 0
    for case_id, wanted in expected.items():
        if wanted["unsupported"]:
            continue
        supported += 1
        row = indexed[case_id]
        assert float(row["robust_reachability"]) == pytest.approx(
            float(row["nominal_reachability"]), abs=1e-10
        )
        assert abs(float(row["initial_expected_ambiguity_units"])) <= 1e-10
    assert supported > 0


def test_intervention_budget_frontier(tmp_path):
    """More intervention opportunities weakly lower, and sometimes change, reachability."""
    zero_root = tmp_path / "zero"
    full_root = tmp_path / "full"
    zero_root.mkdir()
    full_root.mkdir()
    for root, interventions in ((zero_root, "0"), (full_root, "4")):
        copy_surface(SURFACES["hidden"], root)
        subset_cases(root)
        cases = table(root, "robust_budget_cases.csv")
        for row in cases:
            row["intervention_budget_units"] = interventions
        write_table(root / "robust_budget_cases.csv", cases)
    _, zero_rows, zero_expected = assert_surface(zero_root, "intervention-zero")
    _, full_rows, full_expected = assert_surface(full_root, "intervention-full")
    strict = 0
    for case_id in zero_expected:
        if zero_expected[case_id]["unsupported"] or full_expected[case_id]["unsupported"]:
            continue
        zero_value = float(zero_rows[case_id]["robust_reachability"])
        full_value = float(full_rows[case_id]["robust_reachability"])
        assert full_value <= zero_value + 1e-10
        strict += int(full_value < zero_value - 1e-10)
    assert strict > 0


def test_pre_action_joint_plan_is_load_bearing():
    """Require cases whose minimizing plan activates multiple action branches."""
    exercised = 0
    for surface in SURFACES:
        _, _, actual = observed(surface)
        for case_id, expected in EXPECTED[surface].items():
            if (
                not expected["unsupported"]
                and expected["initial_expected_intervention"] > 1
            ):
                assert_result(actual[case_id], expected)
                exercised += 1
    assert exercised >= 8


def test_optional_argument_defaults():
    """Zero and one argument invocations honor both documented default paths."""
    destination = Path("/app/results.csv")
    for command, surface in (
        (["Rscript", "/app/estimate.R"], "public"),
        (["Rscript", "/app/estimate.R", str(SURFACES["hidden"])], "hidden"),
    ):
        destination.unlink(missing_ok=True)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        assert completed.returncode == 0, completed.stderr
        assert destination.is_file() and destination.stat().st_size > 0
        with destination.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        assert rows == observed(surface)[1]


INVALID_MUTATIONS = [
    ("absent-pair", "nominal_transition_counts.csv", "drop-action", "2"),
    ("nonpositive-pair", "nominal_transition_counts.csv", "set", ("count", "0")),
    ("negative-count", "nominal_transition_counts.csv", "first", ("count", "-1")),
    ("negative-budget", "robust_budget_cases.csv", "set", ("budget_units", "-1")),
    (
        "fractional-intervention-budget",
        "robust_budget_cases.csv",
        "set",
        ("intervention_budget_units", "1.5"),
    ),
    ("negative-radius", "robust_budget_cases.csv", "set", ("l1_radius_per_unit", "-0.1")),
    ("bad-horizon", "robust_budget_cases.csv", "set", ("horizon", "0")),
    ("unknown-start", "robust_budget_cases.csv", "set", ("start_state", "other")),
    ("incomplete-policy", "target_policies.csv", "drop-action", "2"),
    ("nonpositive-policy", "target_policies.csv", "set", ("probability", "0")),
    ("policy-simplex", "target_policies.csv", "add", ("probability", "0.05")),
    ("incomplete-profile", "ambiguity_profiles.csv", "drop-action", "2"),
    ("duplicate-profile", "ambiguity_profiles.csv", "duplicate-first", None),
    ("nonpositive-cost", "ambiguity_profiles.csv", "set", ("budget_cost", "0")),
    (
        "nonpositive-multiplier",
        "ambiguity_profiles.csv",
        "set",
        ("radius_multiplier", "0"),
    ),
    (
        "fractional-profile-cap",
        "ambiguity_profiles.csv",
        "set",
        ("max_ambiguity_units", "1.5"),
    ),
]


def mutate(root, file_name, operation, parameter):
    """Apply one disclosed invalid-family mutation to a copied surface."""
    path = root / file_name
    records = table(root, file_name)
    if operation == "drop-action":
        records = [row for row in records if row["action"] != parameter]
    elif operation == "set":
        field, value = parameter
        for row in records:
            row[field] = value
    elif operation == "add":
        field, value = parameter
        for row in records:
            row[field] = str(float(row[field]) + float(value))
    elif operation == "first":
        field, value = parameter
        records[0][field] = value
    elif operation == "duplicate-first":
        seen = set()
        for row in list(records):
            profile_id = row["ambiguity_profile_id"]
            if profile_id not in seen:
                seen.add(profile_id)
                records.append(dict(row))
    else:
        raise AssertionError(operation)
    write_table(path, records)


@pytest.mark.parametrize(
    ("name", "file_name", "operation", "parameter"),
    INVALID_MUTATIONS,
    ids=[item[0] for item in INVALID_MUTATIONS],
)
def test_structural_invalid_variants(
    tmp_path, name, file_name, operation, parameter
):
    """Each disclosed malformed-input family yields typed unsupported rows."""
    copy_surface(SURFACES["hidden"], tmp_path)
    mutate(tmp_path, file_name, operation, parameter)
    _, indexed, expected = assert_surface(tmp_path, "invalid-" + name)
    assert indexed
    for case_id, wanted in expected.items():
        assert wanted["unsupported"] == 1
        row = indexed[case_id]
        assert row["unsupported"] == "1"
        for field in OUTPUT_FIELDS[3:]:
            assert row[field] == ""


def test_repeat_execution_is_byte_deterministic(tmp_path):
    """Repeated executions on the same input produce identical CSV bytes."""
    outputs = []
    for index in range(3):
        path = tmp_path / f"result-{index}.csv"
        completed = subprocess.run(
            ["Rscript", "/app/estimate.R", str(SURFACES["hidden"]), str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1] == outputs[2]
