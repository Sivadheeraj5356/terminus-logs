import csv
import hashlib
import re
from collections import defaultdict

FILE_ORDER = ["lots.csv", "assays.csv", "packaging.csv", "formulas.csv", "orders.csv", "events.csv"]
EVENT_HEADER = ["lot_id", "kind", "day", "grams"]
PRIORITY = {"urgent": 0, "normal": 1, "standby": 2}
PRIORITIES = ["urgent", "normal", "standby"]
ASSAY_HEADER = [
    "lot_id",
    "assay_group",
    "assay_day",
    "valid_through_day",
    "decay_mg_per_g_per_day",
    "uncertainty_growth_mg_per_g_per_day",
]
PACKAGING_HEADER = [
    "lot_id",
    "vial_grams",
    "max_open_cycles",
    "open_decay_mg_per_g_per_day",
    "open_uncertainty_growth_mg_per_g_per_day",
]
MAX_ROWS_PER_FILE = 128
MAX_SURVIVING_LOTS = 12
MAX_SURVIVING_FORMULAS = 16
MAX_SURVIVING_ORDERS = 8
MAX_REQUIRED_GRAMS = 96
MAX_LOTS_PER_ALLOCATION = 3
MAX_LOCAL_PLANS = 4096
MAX_COHORT_PLANS = 2000000
IDENTIFIER = re.compile(r"^[A-Za-z0-9._~-]{1,64}$")


def parse_uint(value, positive=False):
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError(value)
    parsed = int(value)
    if parsed > 2**63 - 1 or (positive and parsed == 0):
        raise ValueError(value)
    return parsed


def validate_identifier(value):
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(value)
    return value


def read_rows(root, name, header):
    with (root / name).open(newline="") as handle:
        rows = list(csv.reader(handle))
    clean = [row for row in rows if not (len(row) == 1 and row[0].strip(" \t") == "")]
    if not clean or clean[0] != header:
        raise ValueError(name)
    if any(len(row) != len(header) for row in clean[1:]):
        raise ValueError(name)
    if len(clean) - 1 > MAX_ROWS_PER_FILE:
        raise ValueError(name)
    return clean[1:]


def lot_better(left, right):
    return (
        -left["potency_mg_per_g"],
        left["uncertainty_mg_per_g"],
        left["expires_day"],
        left["material_id"],
    ) < (
        -right["potency_mg_per_g"],
        right["uncertainty_mg_per_g"],
        right["expires_day"],
        right["material_id"],
    )


def order_better(left, right):
    return (
        PRIORITY[left["priority"]],
        -left["units"],
        left["requested_day"],
        left["product_id"],
    ) < (
        PRIORITY[right["priority"]],
        -right["units"],
        right["requested_day"],
        right["product_id"],
    )


def raw_input_digest(root):
    digest = hashlib.sha256()
    for name in FILE_ORDER:
        raw = (root / name).read_bytes()
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(str(len(raw)).encode())
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
    return digest.hexdigest()


def ceil_div(value, divisor):
    return (value + divisor - 1) // divisor


def allocation_key(lots, take):
    return ",".join(f"{lots[index]['lot_id']}:{grams}" for index, grams in enumerate(take) if grams)


def effective_assay(lot, day):
    age = day - lot["assay_day"]
    potency = max(0, lot["potency_mg_per_g"] - age * lot["decay_mg_per_g_per_day"])
    uncertainty = lot["uncertainty_mg_per_g"] + age * lot["uncertainty_growth_mg_per_g_per_day"]
    return potency, uncertainty


def apply_event_state(grams, status, event):
    if event["kind"] == "loss":
        grams = max(0, grams - event["grams"])
    elif event["kind"] == "restock":
        grams += event["grams"]
    elif event["kind"] == "hold":
        status = "hold"
    else:
        status = "active"
    return grams, status


def lot_state_at(lot, day):
    grams = lot["grams"]
    status = lot["status"]
    for event in lot.get("events", []):
        if event["day"] <= day:
            grams, status = apply_event_state(grams, status, event)
    return grams, status


def allocation_metrics(lots, formula, order, take, substitute_flags, open_ages=None):
    nominal = 0
    open_decay_loss = 0
    open_uncertainty_growth = 0
    group_contributions = defaultdict(int)
    cost = 0
    substitute_grams = 0
    risk = 0
    used = 0
    open_ages = open_ages or {}
    for index, amount in enumerate(take):
        if amount == 0:
            continue
        used += 1
        lot = lots[index]
        potency, uncertainty = effective_assay(lot, order["requested_day"])
        open_age = open_ages.get(index, 0)
        adjusted_potency = max(0, potency - open_age * lot["open_decay_mg_per_g_per_day"])
        adjusted_uncertainty = uncertainty + open_age * lot["open_uncertainty_growth_mg_per_g_per_day"]
        nominal += amount * adjusted_potency
        open_decay_loss += amount * (potency - adjusted_potency)
        open_uncertainty_growth += amount * (adjusted_uncertainty - uncertainty)
        group_contributions[lot["assay_group"]] += amount * adjusted_uncertainty
        cost += amount * lot["cost_cents_per_g"]
        if substitute_flags.get(index, False):
            cost += amount * formula["substitution_penalty_cents_per_g"]
            substitute_grams += amount
        risk += amount * (lot["expires_day"] - order["requested_day"])
    contributions = sorted(group_contributions.values(), reverse=True)
    deduction = sum(contributions[: formula["uncertainty_budget"]])
    mix_loss = formula["mix_loss_mg_per_extra_lot"] * max(0, used - 1)
    robust = max(0, nominal - deduction - mix_loss)
    target = order["units"] * formula["min_robust_potency_mg_per_unit"]
    return {
        "nominal_potency_mg": nominal,
        "open_decay_loss_mg": open_decay_loss,
        "uncertainty_deduction_mg": deduction,
        "open_uncertainty_growth_mg": open_uncertainty_growth,
        "mix_loss_mg": mix_loss,
        "robust_potency_mg": robust,
        "robust_margin_mg": robust - target,
        "cost_cents": cost,
        "substitute_grams": substitute_grams,
        "expiry_risk": risk,
        "used_lot_count": used,
    }


def enumerate_plans(lots, formula, order):
    need = order["units"] * formula["grams_per_unit"]
    target = order["units"] * formula["min_robust_potency_mg_per_unit"]
    candidates = []
    substitute_flags = {}
    for index, lot in enumerate(lots):
        day = order["requested_day"]
        available_grams, available_status = lot_state_at(lot, day)
        if available_status != "active" or available_grams == 0 or lot["expires_day"] < day:
            continue
        if day < lot["assay_day"] or day > lot["valid_through_day"]:
            continue
        substitute = False
        if lot["material_id"] == formula["required_material_id"]:
            pass
        elif formula["substitute_family"] != "-" and lot["family"] == formula["substitute_family"]:
            substitute = True
        else:
            continue
        usable_vial_inventory = available_grams // lot["vial_grams"] * lot["vial_grams"]
        maximum = max(0, usable_vial_inventory - lot["prime_grams"])
        if maximum == 0:
            continue
        candidates.append((index, maximum))
        substitute_flags[index] = substitute
    take = [0] * len(lots)
    plans = []
    suffix_capacity = [0] * (len(candidates) + 1)
    for position in range(len(candidates) - 1, -1, -1):
        suffix_capacity[position] = suffix_capacity[position + 1] + candidates[position][1]

    def visit(position, grams, used_lots):
        if grams > need or used_lots > formula["max_lots"]:
            return
        if grams + suffix_capacity[position] < need:
            return
        if position == len(candidates):
            if grams != need:
                return
            metrics = allocation_metrics(lots, formula, order, take, substitute_flags)
            if metrics["robust_potency_mg"] < target:
                return
            plans.append({**metrics, "allocation_key": allocation_key(lots, take), "take": take.copy()})
            if len(plans) > MAX_LOCAL_PLANS:
                raise ValueError("local plans")
            return
        index, maximum = candidates[position]
        upper = min(maximum, need - grams)
        take[index] = 0
        visit(position + 1, grams, used_lots)
        if used_lots < formula["max_lots"]:
            for amount in range(1, upper + 1):
                take[index] = amount
                visit(position + 1, grams + amount, used_lots + 1)
        take[index] = 0

    visit(0, 0, 0)
    plans.sort(
        key=lambda plan: (
            plan["used_lot_count"],
            plan["cost_cents"],
            plan["uncertainty_deduction_mg"],
            plan["substitute_grams"],
            plan["expiry_risk"],
            -plan["robust_margin_mg"],
            plan["allocation_key"],
        )
    )
    return plans


def cohort_key(selected):
    return ";".join(f"{order_id}={selected[order_id]['allocation_key']}" for order_id in sorted(selected))


def usage_profile(lots, selected, eligible_by_id):
    uses = [defaultdict(int) for _ in lots]
    for order_id, plan in selected.items():
        day = eligible_by_id[order_id]["order"]["requested_day"]
        for index, amount in enumerate(plan["take"]):
            if amount:
                uses[index][day] += amount
    items = []
    open_ages = [dict() for _ in lots]
    valid = True
    for index, lot in enumerate(lots):
        days = sorted(uses[index])
        episodes = []
        position = 0
        while position < len(days):
            start = days[position]
            end = start
            draw = 0
            while position < len(days) and days[position] <= start + lot["open_stability_days"]:
                day = days[position]
                end = day
                draw += uses[index][day]
                open_ages[index][day] = day - start
                position += 1
            consumed = ceil_div(draw + lot["prime_grams"], lot["vial_grams"]) * lot["vial_grams"]
            waste = consumed - draw - lot["prime_grams"]
            episodes.append({"start": start, "end": end, "draw": draw, "consumed": consumed, "waste": waste})
        cycles = len(episodes)
        drawn = sum(item["draw"] for item in episodes)
        primed = cycles * lot["prime_grams"]
        waste = sum(item["waste"] for item in episodes)
        vials = sum(item["consumed"] for item in episodes) // lot["vial_grams"] if lot["vial_grams"] else 0
        if cycles > lot["max_open_cycles"]:
            valid = False
        remaining = lot["grams"]
        status = lot["status"]
        episode_by_start = {item["start"]: item for item in episodes}
        event_days = {event["day"] for event in lot.get("events", [])}
        timeline = sorted(event_days | set(episode_by_start))
        for day in timeline:
            for event in lot.get("events", []):
                if event["day"] == day:
                    remaining, status = apply_event_state(remaining, status, event)
            episode = episode_by_start.get(day)
            if episode is not None:
                if episode["consumed"] > remaining:
                    valid = False
                remaining = max(0, remaining - episode["consumed"])
        items.append(
            {
                "drawn_grams": drawn,
                "prime_cycles": cycles,
                "primed_grams": primed,
                "vial_waste_grams": waste,
                "opened_vial_count": vials,
                "consumed_grams": lot["grams"] - remaining,
                "remaining_grams": remaining,
                "opened": cycles > 0,
                "first_use_day": days[0] if days else None,
                "last_use_day": days[-1] if days else None,
                "status": status,
            }
        )
    adjusted_selected = {}
    for order_id, plan in selected.items():
        item = eligible_by_id[order_id]
        order = item["order"]
        formula = item["formula"]
        day = order["requested_day"]
        ages = {index: open_ages[index][day] for index, amount in enumerate(plan["take"]) if amount}
        substitutes = {
            index: lots[index]["material_id"] != formula["required_material_id"]
            for index, amount in enumerate(plan["take"])
            if amount
        }
        metrics = allocation_metrics(lots, formula, order, plan["take"], substitutes, ages)
        adjusted = {**plan, **metrics}
        adjusted_selected[order_id] = adjusted
        if adjusted["robust_margin_mg"] < 0:
            valid = False
    return {
        "valid": valid,
        "items": items,
        "adjusted_selected": adjusted_selected,
        "opened_lot_count": sum(item["opened"] for item in items),
        "prime_cycle_count": sum(item["prime_cycles"] for item in items),
        "vial_waste_grams": sum(item["vial_waste_grams"] for item in items),
        "opened_vial_count": sum(item["opened_vial_count"] for item in items),
    }


def choose_global(lots, eligible):
    selected = {}
    best = None
    eligible_by_id = {item["order"]["order_id"]: item for item in eligible}

    def visit(position, counts, units):
        nonlocal best
        if position == len(eligible):
            usage = usage_profile(lots, selected, eligible_by_id)
            if not usage["valid"]:
                return
            adjusted = usage["adjusted_selected"]
            cost = sum(plan["cost_cents"] for plan in adjusted.values())
            deduction = sum(plan["uncertainty_deduction_mg"] for plan in adjusted.values())
            substitute_grams = sum(plan["substitute_grams"] for plan in adjusted.values())
            risk = sum(plan["expiry_risk"] for plan in adjusted.values())
            margin = sum(plan["robust_margin_mg"] for plan in adjusted.values())
            key = cohort_key(adjusted)
            objective = tuple(value for rank in range(3) for value in (-counts[rank], -units[rank])) + (
                usage["opened_lot_count"],
                usage["prime_cycle_count"],
                usage["vial_waste_grams"],
                cost,
                deduction,
                substitute_grams,
                risk,
                -margin,
                key,
            )
            if best is None or objective < best["objective"]:
                best = {
                    "objective": objective,
                    "counts": counts.copy(),
                    "units": units.copy(),
                    "cost_cents": cost,
                    "uncertainty_deduction_mg": deduction,
                    "substitute_grams": substitute_grams,
                    "expiry_risk": risk,
                    "robust_margin_mg": margin,
                    "allocation_key": key,
                    "selected": adjusted,
                    "usage": usage,
                }
            return
        item = eligible[position]
        order = item["order"]
        rank = PRIORITY[order["priority"]]
        for plan in item["plans"]:
            selected[order["order_id"]] = plan
            usage = usage_profile(lots, selected, eligible_by_id)
            if usage["valid"]:
                next_counts = counts.copy()
                next_units = units.copy()
                next_counts[rank] += 1
                next_units[rank] += order["units"]
                visit(position + 1, next_counts, next_units)
            selected.pop(order["order_id"])
        visit(position + 1, counts, units)

    visit(0, [0, 0, 0], [0, 0, 0])
    best.pop("objective")
    return best


def expected_report(root, lots_rows, formulas_rows, orders_rows, events_rows):
    if any(len(rows) > MAX_ROWS_PER_FILE for rows in (lots_rows, formulas_rows, orders_rows, events_rows)):
        raise ValueError("row limit")
    lots_by_id = {}
    for row in lots_rows:
        item = {
            "lot_id": validate_identifier(row[0]),
            "material_id": validate_identifier(row[1]),
            "family": validate_identifier(row[2]),
            "potency_mg_per_g": parse_uint(row[3]),
            "uncertainty_mg_per_g": parse_uint(row[4]),
            "grams": parse_uint(row[5]),
            "prime_grams": parse_uint(row[6]),
            "expires_day": parse_uint(row[7]),
            "open_stability_days": parse_uint(row[8]),
            "status": row[9],
            "cost_cents_per_g": parse_uint(row[10]),
        }
        if item["status"] not in {"active", "hold"}:
            raise ValueError("status")
        if item["lot_id"] not in lots_by_id or lot_better(item, lots_by_id[item["lot_id"]]):
            lots_by_id[item["lot_id"]] = item
    if len(lots_by_id) > MAX_SURVIVING_LOTS:
        raise ValueError("lot limit")
    assay_rows = read_rows(root, "assays.csv", ASSAY_HEADER)
    assays = {}
    for row in assay_rows:
        item = {
            "lot_id": validate_identifier(row[0]),
            "assay_group": validate_identifier(row[1]),
            "assay_day": parse_uint(row[2]),
            "valid_through_day": parse_uint(row[3]),
            "decay_mg_per_g_per_day": parse_uint(row[4]),
            "uncertainty_growth_mg_per_g_per_day": parse_uint(row[5]),
        }
        if item["valid_through_day"] < item["assay_day"]:
            raise ValueError("assay interval")
        assays[item["lot_id"]] = item
    packaging_rows = read_rows(root, "packaging.csv", PACKAGING_HEADER)
    packaging = {}
    for row in packaging_rows:
        lot_id = validate_identifier(row[0])
        packaging[lot_id] = {
            "lot_id": lot_id,
            "vial_grams": parse_uint(row[1], positive=True),
            "max_open_cycles": parse_uint(row[2], positive=True),
            "open_decay_mg_per_g_per_day": parse_uint(row[3]),
            "open_uncertainty_growth_mg_per_g_per_day": parse_uint(row[4]),
        }
    for lot_id, item in lots_by_id.items():
        if lot_id not in assays or lot_id not in packaging:
            raise ValueError("metadata")
        item.update(assays[lot_id])
        item.update(packaging[lot_id])
    event_rows = read_rows(root, "events.csv", EVENT_HEADER)
    for sequence, row in enumerate(event_rows):
        lot_id = validate_identifier(row[0])
        kind = row[1]
        day = parse_uint(row[2])
        grams = parse_uint(row[3])
        if kind not in {"loss", "restock", "hold", "release"}:
            raise ValueError("kind")
        item = lots_by_id.get(lot_id)
        if item is None:
            continue
        item.setdefault("events", []).append({"kind": kind, "day": day, "grams": grams, "sequence": sequence})
    for item in lots_by_id.values():
        item.setdefault("events", [])
        item["events"].sort(key=lambda event: (event["day"], event["sequence"]))
    formulas = {}
    for row in formulas_rows:
        item = {
            "product_id": validate_identifier(row[0]),
            "required_material_id": validate_identifier(row[1]),
            "grams_per_unit": parse_uint(row[2], positive=True),
            "min_robust_potency_mg_per_unit": parse_uint(row[3]),
            "uncertainty_budget": parse_uint(row[4]),
            "max_lots": parse_uint(row[5], positive=True),
            "mix_loss_mg_per_extra_lot": parse_uint(row[6]),
            "substitute_family": validate_identifier(row[7]),
            "substitution_penalty_cents_per_g": parse_uint(row[8]),
        }
        if item["max_lots"] > MAX_LOTS_PER_ALLOCATION:
            raise ValueError("max lots")
        formulas[item["product_id"]] = item
    if len(formulas) > MAX_SURVIVING_FORMULAS:
        raise ValueError("formula limit")
    orders_by_id = {}
    for row in orders_rows:
        if row[4] not in PRIORITY:
            raise ValueError("priority")
        item = {
            "order_id": validate_identifier(row[0]),
            "product_id": validate_identifier(row[1]),
            "units": parse_uint(row[2], positive=True),
            "requested_day": parse_uint(row[3]),
            "priority": row[4],
            "max_cost_cents": parse_uint(row[5]),
        }
        if item["order_id"] not in orders_by_id or order_better(item, orders_by_id[item["order_id"]]):
            orders_by_id[item["order_id"]] = item
    if len(orders_by_id) > MAX_SURVIVING_ORDERS:
        raise ValueError("order limit")
    lots = [lots_by_id[key] for key in sorted(lots_by_id)]
    orders = sorted(orders_by_id.values(), key=lambda item: (PRIORITY[item["priority"]], item["requested_day"], item["order_id"]))
    rejections = []
    eligible = []
    for order in orders:
        formula = formulas.get(order["product_id"])
        if formula is None:
            rejections.append({"order_id": order["order_id"], "reason": "UNKNOWN_PRODUCT"})
            continue
        if order["units"] * formula["grams_per_unit"] > MAX_REQUIRED_GRAMS:
            raise ValueError("required grams")
        plans = enumerate_plans(lots, formula, order)
        if not plans:
            rejections.append({"order_id": order["order_id"], "reason": "NO_MATERIAL"})
            continue
        budget_plans = [plan for plan in plans if plan["cost_cents"] <= order["max_cost_cents"]]
        if not budget_plans:
            rejections.append({"order_id": order["order_id"], "reason": "OVER_BUDGET"})
            continue
        eligible.append({"order": order, "formula": formula, "plans": budget_plans})
    cohort_plans = 1
    for item in eligible:
        cohort_plans *= len(item["plans"]) + 1
        if cohort_plans > MAX_COHORT_PLANS:
            raise ValueError("cohort plans")
    winning = choose_global(lots, eligible)
    eligible_by_id = {item["order"]["order_id"]: item for item in eligible}
    filled = []
    for item in eligible:
        order = item["order"]
        plan = winning["selected"].get(order["order_id"])
        if plan is None:
            rejections.append({"order_id": order["order_id"], "reason": "DEFERRED_CAPACITY"})
            continue
        used = []
        for index, amount in enumerate(plan["take"]):
            if amount:
                used.append({"lot_id": lots[index]["lot_id"], "material_id": lots[index]["material_id"], "grams": amount})
        filled.append(
            {
                "order_id": order["order_id"],
                "product_id": order["product_id"],
                "status": "FILLED",
                "grams": order["units"] * item["formula"]["grams_per_unit"],
                "nominal_potency_mg": plan["nominal_potency_mg"],
                "open_decay_loss_mg": plan["open_decay_loss_mg"],
                "uncertainty_deduction_mg": plan["uncertainty_deduction_mg"],
                "open_uncertainty_growth_mg": plan["open_uncertainty_growth_mg"],
                "mix_loss_mg": plan["mix_loss_mg"],
                "robust_potency_mg": plan["robust_potency_mg"],
                "robust_margin_mg": plan["robust_margin_mg"],
                "cost_cents": plan["cost_cents"],
                "substitute_grams": plan["substitute_grams"],
                "lots": used,
            }
        )
    filled.sort(key=lambda item: (PRIORITY[orders_by_id[item["order_id"]]["priority"]], orders_by_id[item["order_id"]]["requested_day"], item["order_id"]))
    rejections.sort(key=lambda item: item["order_id"])
    materials = []
    for index, lot in enumerate(lots):
        usage = winning["usage"]["items"][index]
        materials.append(
            {
                "lot_id": lot["lot_id"],
                "remaining_grams": usage["remaining_grams"],
                "prime_cycles": usage["prime_cycles"],
                "primed_grams": usage["primed_grams"],
                "vial_waste_grams": usage["vial_waste_grams"],
                "opened_vial_count": usage["opened_vial_count"],
                "opened": usage["opened"],
                "first_use_day": usage["first_use_day"],
                "last_use_day": usage["last_use_day"],
                "status": usage["status"],
            }
        )
    audits = []
    for priority in PRIORITIES:
        selected_for_priority = {}
        priority_orders = [item for item in eligible if item["order"]["priority"] == priority]
        totals = {
            "filled_order_count": 0,
            "filled_units": 0,
            "nominal_potency_mg": 0,
            "open_decay_loss_mg": 0,
            "uncertainty_deduction_mg": 0,
            "open_uncertainty_growth_mg": 0,
            "mix_loss_mg": 0,
            "robust_potency_mg": 0,
            "robust_margin_mg": 0,
            "total_cost_cents": 0,
            "substitute_grams": 0,
            "expiry_risk": 0,
        }
        for item in priority_orders:
            order = item["order"]
            plan = winning["selected"].get(order["order_id"])
            if plan is None:
                continue
            selected_for_priority[order["order_id"]] = plan
            totals["filled_order_count"] += 1
            totals["filled_units"] += order["units"]
            for key in (
                "nominal_potency_mg",
                "open_decay_loss_mg",
                "uncertainty_deduction_mg",
                "open_uncertainty_growth_mg",
                "mix_loss_mg",
                "robust_potency_mg",
                "robust_margin_mg",
                "cost_cents",
                "substitute_grams",
                "expiry_risk",
            ):
                output_key = "total_cost_cents" if key == "cost_cents" else key
                totals[output_key] += plan[key]
        profile = usage_profile(lots, selected_for_priority, eligible_by_id)
        audits.append(
            {
                "priority": priority,
                "eligible_order_count": len(priority_orders),
                "filled_order_count": totals["filled_order_count"],
                "filled_units": totals["filled_units"],
                "opened_lot_count": profile["opened_lot_count"],
                "prime_cycle_count": profile["prime_cycle_count"],
                "vial_waste_grams": profile["vial_waste_grams"],
                "opened_vial_count": profile["opened_vial_count"],
                "nominal_potency_mg": totals["nominal_potency_mg"],
                "open_decay_loss_mg": totals["open_decay_loss_mg"],
                "uncertainty_deduction_mg": totals["uncertainty_deduction_mg"],
                "open_uncertainty_growth_mg": totals["open_uncertainty_growth_mg"],
                "mix_loss_mg": totals["mix_loss_mg"],
                "robust_potency_mg": totals["robust_potency_mg"],
                "robust_margin_mg": totals["robust_margin_mg"],
                "total_cost_cents": totals["total_cost_cents"],
                "substitute_grams": totals["substitute_grams"],
                "expiry_risk": totals["expiry_risk"],
                "allocation_key": cohort_key(selected_for_priority),
            }
        )
    input_digest = raw_input_digest(root)
    summary = {
        "filled_count": len(filled),
        "rejected_count": len(rejections),
        "total_cost_cents": sum(item["cost_cents"] for item in filled),
        "total_dispensed_grams": sum(item["grams"] for item in filled),
        "total_prime_cycles": sum(item["prime_cycles"] for item in materials),
        "total_prime_grams": sum(item["primed_grams"] for item in materials),
        "total_vial_waste_grams": sum(item["vial_waste_grams"] for item in materials),
        "total_opened_vials": sum(item["opened_vial_count"] for item in materials),
        "opened_lot_count": sum(item["opened"] for item in materials),
        "total_open_decay_loss_mg": sum(item["open_decay_loss_mg"] for item in filled),
        "total_open_uncertainty_growth_mg": sum(item["open_uncertainty_growth_mg"] for item in filled),
        "robust_margin_mg": sum(item["robust_margin_mg"] for item in filled),
        "digest": "",
    }
    rows = [f"I|{input_digest}"]
    for audit in audits:
        rows.append(
            "A|{priority}|{eligible_order_count}|{filled_order_count}|{filled_units}|{opened_lot_count}|{prime_cycle_count}|{vial_waste_grams}|{opened_vial_count}|{nominal_potency_mg}|{open_decay_loss_mg}|{uncertainty_deduction_mg}|{open_uncertainty_growth_mg}|{mix_loss_mg}|{robust_potency_mg}|{robust_margin_mg}|{total_cost_cents}|{substitute_grams}|{expiry_risk}|{allocation_key}".format(**audit)
        )
    for item in filled:
        key = ",".join(f"{use['lot_id']}:{use['grams']}" for use in item["lots"])
        rows.append(
            f"F|{item['order_id']}|{item['cost_cents']}|{item['nominal_potency_mg']}|{item['open_decay_loss_mg']}|{item['uncertainty_deduction_mg']}|{item['open_uncertainty_growth_mg']}|{item['mix_loss_mg']}|{item['robust_potency_mg']}|{item['robust_margin_mg']}|{item['substitute_grams']}|{key}"
        )
    for item in rejections:
        rows.append(f"R|{item['order_id']}|{item['reason']}")
    for item in materials:
        first = "-" if item["first_use_day"] is None else str(item["first_use_day"])
        last = "-" if item["last_use_day"] is None else str(item["last_use_day"])
        opened = "true" if item["opened"] else "false"
        rows.append(
            f"M|{item['lot_id']}|{item['remaining_grams']}|{item['prime_cycles']}|{item['primed_grams']}|{item['vial_waste_grams']}|{item['opened_vial_count']}|{opened}|{first}|{last}|{item['status']}"
        )
    summary["digest"] = hashlib.sha256(("\n".join(rows) + "\n").encode()).hexdigest()
    return {
        "schema": "amberglass.v6",
        "input_digest": input_digest,
        "orders": filled,
        "rejections": rejections,
        "materials": materials,
        "cohort_audit": audits,
        "summary": summary,
    }
