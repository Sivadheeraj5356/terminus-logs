"""Verifier for switch-binning. The agent's main.rs is recompiled under a fixed verifier-owned rustc
command and run on the shipped design slate; the plan it prints is graded on held-out true acceptance
rates the agent never sees. A design's release chance is 1-(1-p_true)^n over its die count, the floor is
the worst design in the slate, and spend is measured against a sealed ceiling. The same binary is rerun
on a disjoint holdout slate so a table wired to the shipped ids cannot pass. All seal/build/run fixtures
are in conftest.py.
"""


def release_chances(plan, truth):
    """Per-design release chance 1-(1-p)^n on the true rates, paired with each design id."""
    out = {}
    for did, p in truth.items():
        n = plan[did]["probe_dies"] + plan[did]["lab_dies"]
        out[did] = 1.0 - (1.0 - p) ** n
    return out


def weakest(plan, truth):
    chances = release_chances(plan, truth)
    did = min(chances, key=chances.get)
    return did, chances[did]


def total_spend(plan, costs):
    total = 0.0
    for did, row in plan.items():
        total += row["probe_dies"] * costs[did]["probe_cost"]
        total += row["lab_dies"] * costs[did]["lab_cost"]
    return total


def die_total(plan):
    return sum(r["probe_dies"] + r["lab_dies"] for r in plan.values())


# ---- the binary compiled, and the plan is worked from the data (not a baked-in table) ----
def test_source_compiles(bin_path):
    """The submitted Rust builds under the verifier's own rustc invocation."""
    assert bin_path.exists()


def test_ids_follow_the_instance(plan, holdout_plan):
    """Rerun on a disjoint slate the binary emits THAT slate's ids: proof the counts are computed from
    the inputs rather than read from a fixed table keyed to the shipped designs."""
    assert set(holdout_plan) and set(holdout_plan).isdisjoint(plan), (
        "the builder prints the shipped ids on a disjoint slate; counts must be worked from the data"
    )


def test_counts_respond_to_inputs(plan, plan_perturbed):
    """Lift every gate_grade and mark every logged die passed: rates read stronger, so a genuine builder
    commits strictly fewer dies, while a precomputed plan does not budge."""
    assert plan != plan_perturbed, "plan unchanged on perturbed inputs; counts must be computed at run time"
    assert die_total(plan_perturbed) < die_total(plan), (
        f"stronger inputs should cut the die count, but the total went {die_total(plan)} -> "
        f"{die_total(plan_perturbed)}"
    )


# ---- shape and validity of the shipped-slate plan ----
def test_slate_is_complete(plan, truth):
    """Exactly the shipped designs appear, one entry each."""
    assert set(plan) == set(truth), "plan must cover exactly the shipped designs"


def test_counts_are_nonneg_ints(plan):
    """Every in-house and outside die count is a non-negative integer."""
    for did, row in plan.items():
        a, b = row["probe_dies"], row["lab_dies"]
        assert isinstance(a, int) and isinstance(b, int), f"{did}: die counts must be integers"
        assert a >= 0 and b >= 0, f"{did}: die counts must be non-negative"


def test_probe_allotment_not_exceeded(plan, threshold):
    """In-house dies summed over the slate stay within the shared probe allotment."""
    used = sum(r["probe_dies"] for r in plan.values())
    cap = threshold["probe_capacity"]
    assert used <= cap, f"in-house dies {used} exceed the probe capacity {cap}"


# ---- the two held-out gates on the shipped slate ----
def test_worst_design_clears_floor(plan, truth, threshold):
    """On the held-out true rates the weakest design's release chance clears the signoff floor."""
    floor = threshold["signoff_floor"]
    did, chance = weakest(plan, truth)
    n = plan[did]["probe_dies"] + plan[did]["lab_dies"]
    assert chance >= floor, f"floor {floor} missed: weakest design {did} at {chance:.4f} (n={n})"


def test_spend_under_ceiling(plan, threshold, costs):
    """Committed spend, priced from the sealed cost snapshot, stays within the sealed ceiling."""
    ceiling = threshold["cost_ceiling"]
    spend = total_spend(plan, costs)
    assert spend <= ceiling, f"committed spend {spend:.2f} exceeds ceiling {ceiling:.2f}"


# ---- the same gates rerun on the disjoint holdout slate ----
def test_holdout_slate_is_complete(holdout_plan, holdout_truth):
    """The holdout plan covers exactly the holdout designs (a table wired to the shipped slate fails)."""
    assert set(holdout_plan) == set(holdout_truth), "holdout plan must cover exactly the holdout designs"


def test_holdout_counts_are_nonneg_ints(holdout_plan):
    """Every holdout die count is a non-negative integer."""
    for did, row in holdout_plan.items():
        a, b = row["probe_dies"], row["lab_dies"]
        assert isinstance(a, int) and isinstance(b, int), f"{did}: die counts must be integers"
        assert a >= 0 and b >= 0, f"{did}: die counts must be non-negative"


def test_holdout_probe_allotment_not_exceeded(holdout_plan, holdout_threshold):
    """In-house dies on the holdout slate stay within the holdout probe allotment."""
    used = sum(r["probe_dies"] for r in holdout_plan.values())
    cap = holdout_threshold["probe_capacity"]
    assert used <= cap, f"holdout in-house dies {used} exceed the capacity {cap}"


def test_holdout_worst_design_clears_floor(holdout_plan, holdout_truth, holdout_threshold):
    """The weakest holdout design clears the holdout floor on the holdout true rates."""
    floor = holdout_threshold["signoff_floor"]
    did, chance = weakest(holdout_plan, holdout_truth)
    assert chance >= floor, f"holdout floor {floor} missed: weakest design {did} at {chance:.4f}"


def test_holdout_spend_under_ceiling(holdout_plan, holdout_threshold, holdout_costs):
    """Holdout committed spend stays within the holdout ceiling."""
    ceiling = holdout_threshold["cost_ceiling"]
    spend = total_spend(holdout_plan, holdout_costs)
    assert spend <= ceiling, f"holdout committed spend {spend:.2f} exceeds ceiling {ceiling:.2f}"
