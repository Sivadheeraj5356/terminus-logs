"""Verifier for anode-stringing. Rebuilds the stringer from the agent's main.c with a fixed
verifier-owned cc command and grades the plan: the end-of-life protection chance 1-(1-p_true)^n uses
held-out true survival rates, the floor binds jointly on the worst zone, committed cost is measured
against a sealed ceiling, and the same binary is rerun on a disjoint holdout. Fixtures/sealing live
in conftest.py.
"""


def worst_protection(plan, truth):
    """The plan's worst-of-array end-of-life protection chance on the true rates, and its binding zone."""
    worst, worst_zn = 1.0, None
    for zid, p in truth.items():
        n = plan[zid]["stock_anodes"] + plan[zid]["extra_anodes"]
        hold = 1.0 - (1.0 - p) ** n
        if hold < worst:
            worst, worst_zn = hold, zid
    return worst, worst_zn


def committed_cost(plan, costs):
    cost = 0.0
    for zid, b in plan.items():
        cost += b["stock_anodes"] * costs[zid]["stock_cost"]
        cost += b["extra_anodes"] * costs[zid]["extra_cost"]
    return cost


def _assert_feasible(plan, expected_ids, stock_budget):
    """Structural feasibility, independent of the hidden rates: exactly the expected zones, each count
    a non-negative integer, stock anodes within the shared allowance. Floor/ceiling are not checked
    here -- they grade against sealed rates the perturbed inputs have no matching truth for."""
    assert set(plan) == expected_ids, "plan must cover exactly the expected zones"
    used = 0
    for zid, b in plan.items():
        s, x = b["stock_anodes"], b["extra_anodes"]
        assert isinstance(s, int) and isinstance(x, int), f"{zid}: anode counts must be integers"
        assert s >= 0 and x >= 0, f"{zid}: anode counts must be non-negative"
        used += s
    assert used <= stock_budget, f"stock anodes {used} exceed the stock budget {stock_budget}"


def test_build_succeeds(bin_path):
    """The agent's C code compiles under the verifier-owned cc command."""
    assert bin_path.exists()


def test_computes_from_data_not_a_static_table(plan, holdout_plan):
    """Rerun on a disjoint zone list, the binary must emit THAT list's ids, not the shipped ones --
    the plan is computed from the input, not a fixed public table."""
    assert set(holdout_plan) and set(holdout_plan).isdisjoint(plan), (
        "stringer emits the same zone ids on a disjoint instance; counts must come from the data"
    )


def test_every_zone_planned(plan, truth):
    """The plan covers exactly the shipped zones, one entry each."""
    assert set(plan) == set(truth), "plan must cover exactly the shipped zones"


def test_anode_counts_are_valid_nonneg_ints(plan):
    """Every stock/extra anode count is a non-negative integer."""
    for zid, b in plan.items():
        s, x = b["stock_anodes"], b["extra_anodes"]
        assert isinstance(s, int) and isinstance(x, int), f"{zid}: anode counts must be integers"
        assert s >= 0 and x >= 0, f"{zid}: anode counts must be non-negative"


def test_stock_budget_not_exceeded(plan, threshold):
    """Total stock anodes stay within the shared stock allowance."""
    cap = threshold["anode_stock_budget"]
    used = sum(b["stock_anodes"] for b in plan.values())
    assert used <= cap, f"stock anodes {used} exceed the stock budget {cap}"


def test_protection_floor_holds_on_service_life(plan, truth, threshold):
    """The worst zone's protection chance on the held-out true rates clears the floor (the joint gate)."""
    floor = threshold["protection_floor"]
    worst, worst_zn = worst_protection(plan, truth)
    n = plan[worst_zn]["stock_anodes"] + plan[worst_zn]["extra_anodes"]
    assert worst >= floor, f"protection floor {floor} missed: worst zone {worst_zn} at {worst:.4f} (n={n})"


def test_committed_cost_within_ceiling(plan, threshold, costs):
    """Total committed cost stays within the sealed cost ceiling."""
    ceiling = threshold["cost_ceiling"]
    cost = committed_cost(plan, costs)
    assert cost <= ceiling, f"committed cost {cost:.2f} exceeds ceiling {ceiling:.2f}"


def test_plan_responds_to_survival_log(plan, plan_survival_perturbed, threshold):
    """Perturb the survival log alone (resistivity held fixed): all-lasted records read as stronger
    survival, so a genuine sizer strings strictly fewer anodes while a baked-in table holds. The
    perturbed plan must also stay structurally feasible, not just move on direction."""
    total = sum(b["stock_anodes"] + b["extra_anodes"] for b in plan.values())
    total_pert = sum(b["stock_anodes"] + b["extra_anodes"] for b in plan_survival_perturbed.values())
    assert plan != plan_survival_perturbed, "plan did not change when the survival log changed; counts must be computed at run time"
    assert total_pert < total, (
        f"an all-lasted survival log reads as higher survival, so fewer anodes should be strung, "
        f"but totals went {total} -> {total_pert}"
    )
    _assert_feasible(plan_survival_perturbed, set(plan), threshold["anode_stock_budget"])


def test_plan_responds_to_resistivity(plan, plan_resistivity_perturbed, threshold):
    """Perturb soil resistivity alone (survival log held fixed): resistivity is the signal named for
    zones whose own tally is too thin to trust, so a data-driven plan must move when it changes. A
    sizer that reads only the per-zone survival count -- ignoring the resistivity column, e.g. a fixed
    multiple of the naive count -- emits an identical plan and fails here. The moved plan must also
    stay structurally feasible."""
    changed = [
        z for z in plan
        if plan[z]["stock_anodes"] + plan[z]["extra_anodes"]
        != plan_resistivity_perturbed[z]["stock_anodes"] + plan_resistivity_perturbed[z]["extra_anodes"]
    ]
    assert changed, (
        "the plan did not respond to a change in soil resistivity; the count for at least some zones "
        "must depend on the resistivity column, not the survival log alone"
    )
    _assert_feasible(plan_resistivity_perturbed, set(plan), threshold["anode_stock_budget"])


def test_beats_naive_baseline(plan, holdout_plan, truth, holdout_truth, threshold, holdout_threshold, baseline):
    """The plain stringer reads each zone's rate off its own (often sparse, over-optimistic) record,
    under-strings the weak zones and misses the joint floor -- shipped set and disjoint holdout alike;
    a passing plan must clear the floor it falls short of, on both."""
    floor, hfloor = threshold["protection_floor"], holdout_threshold["protection_floor"]
    assert baseline["naive_worst_protection"] < floor, "baseline unexpectedly cleared the floor"
    assert baseline["holdout_naive_worst_protection"] < hfloor, "baseline unexpectedly cleared the holdout floor"
    agent_worst, _ = worst_protection(plan, truth)
    holdout_agent_worst, _ = worst_protection(holdout_plan, holdout_truth)
    assert agent_worst >= floor and holdout_agent_worst >= hfloor, (
        f"plan must beat the naive baseline by clearing the floor it misses "
        f"(agent {agent_worst:.4f}, holdout {holdout_agent_worst:.4f})"
    )


# ---- holdout instance: the full plan/floor/budget/cost gates, rerun on unseen zones/log/policy ----
def test_holdout_every_zone_planned(holdout_plan, holdout_truth):
    """The holdout plan covers exactly the holdout zones (a hardcoded shipped plan fails here)."""
    assert set(holdout_plan) == set(holdout_truth), "holdout plan must cover exactly the holdout zones"


def test_holdout_anode_counts_are_valid_nonneg_ints(holdout_plan):
    """Every holdout anode count is a non-negative integer."""
    for zid, b in holdout_plan.items():
        s, x = b["stock_anodes"], b["extra_anodes"]
        assert isinstance(s, int) and isinstance(x, int), f"{zid}: anode counts must be integers"
        assert s >= 0 and x >= 0, f"{zid}: anode counts must be non-negative"


def test_holdout_stock_budget_not_exceeded(holdout_plan, holdout_threshold):
    """Total holdout stock anodes stay within the holdout stock allowance."""
    cap = holdout_threshold["anode_stock_budget"]
    used = sum(b["stock_anodes"] for b in holdout_plan.values())
    assert used <= cap, f"holdout stock anodes {used} exceed the budget {cap}"


def test_holdout_protection_floor_holds(holdout_plan, holdout_truth, holdout_threshold):
    """The worst holdout zone's protection chance on the holdout true rates clears the holdout floor."""
    floor = holdout_threshold["protection_floor"]
    worst, worst_zn = worst_protection(holdout_plan, holdout_truth)
    assert worst >= floor, f"holdout floor {floor} missed: worst zone {worst_zn} at {worst:.4f}"


def test_holdout_committed_cost_within_ceiling(holdout_plan, holdout_threshold, holdout_costs):
    """Total holdout committed cost stays within the holdout cost ceiling."""
    ceiling = holdout_threshold["cost_ceiling"]
    cost = committed_cost(holdout_plan, holdout_costs)
    assert cost <= ceiling, f"holdout committed cost {cost:.2f} exceeds ceiling {ceiling:.2f}"
