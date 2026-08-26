"""Verifier for wick-proving. The agent's main.rs is recompiled under a fixed verifier-owned rustc
call, run over the shipped design board, and its printed plan is graded: the clean-burn chance
1-(1-p_true)^n is taken on held-out true rates, the floor has to hold on the single weakest design,
and the committed pour cost is measured against a sealed ceiling. That same binary is then run once
more on a separate holdout board, so a plan pinned to the shipped designs cannot slide through. The
seal, the compile, and the run fixtures all come from conftest.py.
"""


def worst_burns_clean(plan, truth):
    """The lowest 1-(1-p)^n over the board on the true rates, with the design that produces it."""
    worst, worst_id = 1.0, None
    for did, p in truth.items():
        n = plan[did]["line_pours"] + plan[did]["shop_pours"]
        chance = 1.0 - (1.0 - p) ** n
        if chance < worst:
            worst, worst_id = chance, did
    return worst, worst_id


def committed_cost(plan, costs):
    total = 0.0
    for did, b in plan.items():
        total += b["line_pours"] * costs[did]["cost_line"]
        total += b["shop_pours"] * costs[did]["cost_shop"]
    return total


def test_build_succeeds(bin_path):
    """The agent's Rust source compiled under the verifier's own rustc call."""
    assert bin_path.exists()


def test_computes_from_data_not_a_static_table(plan, holdout_plan):
    """On a separate board the binary has to print THAT board's ids rather than the shipped ones,
    which shows the counts are derived from the inputs and not lifted from a table baked into the code."""
    assert set(holdout_plan) and set(holdout_plan).isdisjoint(plan), (
        "chandler prints the same design ids on a disjoint board; counts must be computed from the data"
    )


def test_every_design_planned(plan, truth):
    """Every shipped design is covered, exactly one plan entry each."""
    assert set(plan) == set(truth), "plan must cover exactly the shipped designs"


def test_pours_are_valid_nonneg_ints(plan):
    """On each design both route counts are non-negative integers."""
    for did, b in plan.items():
        line, shop = b["line_pours"], b["shop_pours"]
        assert isinstance(line, int) and isinstance(shop, int), f"{did}: pour counts must be integers"
        assert line >= 0 and shop >= 0, f"{did}: pour counts must be non-negative"


def test_line_capacity_not_exceeded(plan, threshold):
    """In-house line pours summed over the board stay within the shared line pool."""
    cap = threshold["line_capacity"]
    used = sum(b["line_pours"] for b in plan.values())
    assert used <= cap, f"in-house line pours {used} exceed the line capacity {cap}"


def test_line_used_before_shop(plan, threshold):
    """The cheap in-house line is one shared pool, spent before the dearer chandler: if any design
    carries shop pours, the board's line pours have to fill the whole capacity. Booking the chandler
    while in-house slots sit idle wastes spend on a plan a line-first split would pour cheaper."""
    cap = threshold["line_capacity"]
    line_used = sum(b["line_pours"] for b in plan.values())
    shop_used = sum(b["shop_pours"] for b in plan.values())
    assert shop_used == 0 or line_used >= cap, (
        f"shop pours booked ({shop_used}) while the in-house line sits idle "
        f"(line {line_used} of capacity {cap}); the cheaper shared line must be filled first"
    )


def test_burn_floor_holds(plan, truth, threshold):
    """On the held-out true rates the weakest design's clean-burn chance reaches the floor (joint gate)."""
    floor = threshold["burn_floor"]
    worst, worst_id = worst_burns_clean(plan, truth)
    n = plan[worst_id]["line_pours"] + plan[worst_id]["shop_pours"]
    assert worst >= floor, f"burn floor {floor} missed: weakest design {worst_id} at {worst:.4f} (n={n})"


def test_committed_cost_within_ceiling(plan, threshold, costs):
    """The whole committed pour cost stays within the sealed cost ceiling."""
    ceiling = threshold["cost_ceiling"]
    total = committed_cost(plan, costs)
    assert total <= ceiling, f"committed cost {total:.2f} exceeds ceiling {ceiling:.2f}"


def test_plan_responds_to_input_data(plan, plan_perturbed):
    """When the inputs shift the plan shifts with them, and the right way: an all-clean record and a
    higher blend_grade read as stronger rates, so a real planner commits strictly fewer candles while
    a table baked into the code does not budge."""
    total = sum(b["line_pours"] + b["shop_pours"] for b in plan.values())
    total_pert = sum(b["line_pours"] + b["shop_pours"] for b in plan_perturbed.values())
    assert plan != plan_perturbed, "plan did not change on perturbed inputs; counts must be computed at run time"
    assert total_pert < total, (
        f"perturbed inputs read as all-clean, so rates rise and fewer candles should be committed, "
        f"but totals went {total} -> {total_pert}"
    )


# ---- holdout instance: the full plan/floor/capacity/cost gates, rerun on the unseen board/log/policy ----
def test_holdout_every_design_planned(holdout_plan, holdout_truth):
    """The holdout plan covers exactly the holdout designs (a plan hardcoded to the shipped board fails)."""
    assert set(holdout_plan) == set(holdout_truth), "holdout plan must cover exactly the holdout designs"


def test_holdout_pours_are_valid_nonneg_ints(holdout_plan):
    """Each holdout route count is a non-negative integer."""
    for did, b in holdout_plan.items():
        line, shop = b["line_pours"], b["shop_pours"]
        assert isinstance(line, int) and isinstance(shop, int), f"{did}: pour counts must be integers"
        assert line >= 0 and shop >= 0, f"{did}: pour counts must be non-negative"


def test_holdout_line_capacity_not_exceeded(holdout_plan, holdout_threshold):
    """Holdout in-house line pours summed over the board stay within the holdout line capacity."""
    cap = holdout_threshold["line_capacity"]
    used = sum(b["line_pours"] for b in holdout_plan.values())
    assert used <= cap, f"holdout in-house line pours {used} exceed the capacity {cap}"


def test_holdout_line_used_before_shop(holdout_plan, holdout_threshold):
    """On the holdout board too, the shared in-house line is spent before the chandler: shop pours
    are allowed only once the whole holdout line capacity is filled."""
    cap = holdout_threshold["line_capacity"]
    line_used = sum(b["line_pours"] for b in holdout_plan.values())
    shop_used = sum(b["shop_pours"] for b in holdout_plan.values())
    assert shop_used == 0 or line_used >= cap, (
        f"holdout shop pours booked ({shop_used}) while the in-house line sits idle "
        f"(line {line_used} of capacity {cap}); the cheaper shared line must be filled first"
    )


def test_holdout_burn_floor_holds(holdout_plan, holdout_truth, holdout_threshold):
    """On the holdout true rates the weakest holdout design's clean-burn chance reaches the holdout floor."""
    floor = holdout_threshold["burn_floor"]
    worst, worst_id = worst_burns_clean(holdout_plan, holdout_truth)
    assert worst >= floor, f"holdout floor {floor} missed: weakest design {worst_id} at {worst:.4f}"


def test_holdout_committed_cost_within_ceiling(holdout_plan, holdout_threshold, holdout_costs):
    """The whole holdout committed pour cost stays within the holdout cost ceiling."""
    ceiling = holdout_threshold["cost_ceiling"]
    total = committed_cost(holdout_plan, holdout_costs)
    assert total <= ceiling, f"holdout committed cost {total:.2f} exceeds ceiling {ceiling:.2f}"
