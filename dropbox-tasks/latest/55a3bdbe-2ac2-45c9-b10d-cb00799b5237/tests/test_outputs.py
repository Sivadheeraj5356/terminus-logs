"""Verifier for keeper-framing. Rebuilds the framer from the agent's main.rs with a fixed
verifier-owned rustc command, runs it against the shipped shoot list, and grades the plan: keeper
chance 1-(1-p_true)^n uses held-out true rates, the floor binds jointly on the worst subject, and
cost is checked against a sealed ceiling. The same binary is rerun against a disjoint holdout fleet
so a plan hardcoded to the shipped subjects cannot pass. Sealing, the build, and the run fixtures
live in conftest.py.
"""

def worst_keeper(plan, truth):
    """The plan's worst-of-array keeper probability on the true rates, and the subject that binds it."""
    worst, worst_su = 1.0, None
    for sid, p in truth.items():
        n = plan[sid]["hide_frames"] + plan[sid]["guided_frames"]
        odds = 1.0 - (1.0 - p) ** n
        if odds < worst:
            worst, worst_su = odds, sid
    return worst, worst_su


def committed_cost(plan, costs):
    cost = 0.0
    for sid, b in plan.items():
        cost += b["hide_frames"] * costs[sid]["hide_cost"]
        cost += b["guided_frames"] * costs[sid]["guide_cost"]
    return cost


def test_build_succeeds(bin_path):
    """The agent's Rust code compiles under the verifier-owned rustc command."""
    assert bin_path.exists()


def test_computes_from_data_not_a_static_table(plan, holdout_plan):
    """Rerun on a disjoint subject fleet the binary must emit THAT fleet's ids, not the shipped ones:
    a behavioural check that the plan is computed from the input rather than a fixed public table."""
    assert set(holdout_plan) and set(holdout_plan).isdisjoint(plan), (
        "framer emits the same subject ids on a disjoint instance; counts must come from the data"
    )


def test_every_subject_planned(plan, truth):
    """The plan covers exactly the shipped subjects, one entry each."""
    assert set(plan) == set(truth), "plan must cover exactly the shipped subjects"


def test_frames_are_valid_nonneg_ints(plan):
    """Every hide/guided frame count is a non-negative integer."""
    for sid, b in plan.items():
        s, d = b["hide_frames"], b["guided_frames"]
        assert isinstance(s, int) and isinstance(d, int), f"{sid}: frame counts must be integers"
        assert s >= 0 and d >= 0, f"{sid}: frame counts must be non-negative"


def test_hide_budget_not_exceeded(plan, threshold):
    """Total hide frames stay within the fleet-wide hide frame budget."""
    cap = threshold["hide_frame_budget"]
    used = sum(b["hide_frames"] for b in plan.values())
    assert used <= cap, f"hide frames {used} exceed the hide frame budget {cap}"


def test_keeper_floor_holds_on_outing(plan, truth, threshold):
    """The worst subject's keeper chance on the held-out true rates clears the floor (the joint gate)."""
    floor = threshold["keeper_floor"]
    worst, worst_su = worst_keeper(plan, truth)
    n = plan[worst_su]["hide_frames"] + plan[worst_su]["guided_frames"]
    assert worst >= floor, f"keeper floor {floor} missed: worst subject {worst_su} at {worst:.4f} (n={n})"


def test_committed_cost_within_ceiling(plan, threshold, costs):
    """Total committed cost stays within the sealed cost ceiling."""
    ceiling = threshold["cost_ceiling"]
    cost = committed_cost(plan, costs)
    assert cost <= ceiling, f"committed cost {cost:.2f} exceeds ceiling {ceiling:.2f}"


def test_plan_responds_to_input_data(plan, plan_perturbed):
    """The plan changes, and in the right direction, when inputs change: perturbed all-keeper and
    higher-showiness inputs read as stronger rates, so a genuine sizer commits strictly fewer frames
    while a baked-in table does not move."""
    total = sum(b["hide_frames"] + b["guided_frames"] for b in plan.values())
    total_pert = sum(b["hide_frames"] + b["guided_frames"] for b in plan_perturbed.values())
    assert plan != plan_perturbed, "plan did not change on perturbed inputs; counts must be computed at run time"
    assert total_pert < total, (
        f"perturbed inputs read as all-keeper, so rates rise and fewer frames should be committed, "
        f"but totals went {total} -> {total_pert}"
    )


# ---- holdout instance: the full plan/floor/budget/cost gates, rerun on unseen subject/log/policy ----
def test_holdout_every_subject_planned(holdout_plan, holdout_truth):
    """The holdout plan covers exactly the holdout subjects (a hardcoded shipped plan fails here)."""
    assert set(holdout_plan) == set(holdout_truth), "holdout plan must cover exactly the holdout subjects"


def test_holdout_frames_are_valid_nonneg_ints(holdout_plan):
    """Every holdout frame count is a non-negative integer."""
    for sid, b in holdout_plan.items():
        s, d = b["hide_frames"], b["guided_frames"]
        assert isinstance(s, int) and isinstance(d, int), f"{sid}: frame counts must be integers"
        assert s >= 0 and d >= 0, f"{sid}: frame counts must be non-negative"


def test_holdout_hide_budget_not_exceeded(holdout_plan, holdout_threshold):
    """Total holdout hide frames stay within the holdout hide frame budget."""
    cap = holdout_threshold["hide_frame_budget"]
    used = sum(b["hide_frames"] for b in holdout_plan.values())
    assert used <= cap, f"holdout hide frames {used} exceed the budget {cap}"


def test_holdout_keeper_floor_holds(holdout_plan, holdout_truth, holdout_threshold):
    """The worst holdout subject's keeper chance on the holdout true rates clears the holdout floor."""
    floor = holdout_threshold["keeper_floor"]
    worst, worst_su = worst_keeper(holdout_plan, holdout_truth)
    assert worst >= floor, f"holdout floor {floor} missed: worst subject {worst_su} at {worst:.4f}"


def test_holdout_committed_cost_within_ceiling(holdout_plan, holdout_threshold, holdout_costs):
    """Total holdout committed cost stays within the holdout cost ceiling."""
    ceiling = holdout_threshold["cost_ceiling"]
    cost = committed_cost(holdout_plan, holdout_costs)
    assert cost <= ceiling, f"holdout committed cost {cost:.2f} exceeds ceiling {ceiling:.2f}"
