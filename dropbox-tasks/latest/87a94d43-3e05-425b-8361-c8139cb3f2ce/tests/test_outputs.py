import copy
import hashlib
import json
import os
import random
import subprocess
from pathlib import Path


INPUT = Path("/app/match.json")
OUTPUT = Path("/app/output/result.json")
BINARY = Path("/app/adjudicate")
SOURCE = Path("/app/main.go")
PUBLIC_BYTES = INPUT.read_bytes()
PUBLIC_SHA256 = "a153464aecb521f775ecba962fcdadd238510af882975ec7bd7d54dca1a9dffd"
OUTPUT_KEYS = ["status", "selected", "scores", "units", "winner"]


def replay(spec, selected):
    cells = {c["id"]: c for c in spec["cells"]}
    units = {u["id"]: {**u, "alive": True} for u in spec["units"]}
    scores = {p: 0 for p in spec["players"]}
    patches = {(r["round"], r["unit"]): r["action"] for r in spec["rulings"] if r["id"] in selected}

    def adjacent(a, b):
        return b in cells[a]["neighbors"]

    for ri, baseline in enumerate(spec["rounds"]):
        commands = {a["unit"]: a for a in baseline}
        for (round_index, unit_id), action in patches.items():
            if round_index == ri:
                commands[unit_id] = action
        positions = {u["cell"]: uid for uid, u in units.items() if u["alive"]}
        intents, counts = {}, {}
        for uid, u in units.items():
            action = commands.get(uid, {"type": "wait"})
            if not u["alive"] or action["type"] != "move" or action.get("to") not in cells:
                continue
            target = action["to"]
            cost = cells[target]["move_cost"]
            if not adjacent(u["cell"], target) or u["energy"] < cost:
                continue
            u["energy"] -= cost
            intents[uid] = target
            counts[target] = counts.get(target, 0) + 1
        unique = {uid: counts[to] == 1 for uid, to in intents.items()}
        state, success = {}, {}

        def resolves(uid):
            if not unique.get(uid, False):
                return False
            if state.get(uid) == 1:
                return True
            if state.get(uid) == 2:
                return success[uid]
            state[uid] = 1
            occupant = positions.get(intents[uid])
            result = occupant is None or (unique.get(occupant, False) and resolves(occupant))
            state[uid] = 2
            success[uid] = result
            return result

        for uid in intents:
            resolves(uid)
        for uid, succeeds in success.items():
            if succeeds:
                units[uid]["cell"] = intents[uid]

        shields = {}
        for uid, u in units.items():
            action = commands.get(uid, {"type": "wait"})
            if u["alive"] and action["type"] == "guard" and u["energy"] >= 1:
                u["energy"] -= 1
                shields[uid] = u["strength"]
        damage = {}
        for uid, u in units.items():
            action = commands.get(uid, {"type": "wait"})
            if not u["alive"] or action["type"] != "strike" or u["energy"] < 1:
                continue
            target = units.get(action.get("target"))
            if target is None or not target["alive"] or target["player"] == u["player"] or not adjacent(u["cell"], target["cell"]):
                continue
            u["energy"] -= 1
            damage[target["id"]] = damage.get(target["id"], 0) + u["strength"]
        for uid, incoming in damage.items():
            units[uid]["health"] -= max(0, incoming - shields.get(uid, 0))
        for u in units.values():
            if u["alive"] and u["health"] <= 0:
                u["alive"] = False
        for u in units.values():
            if u["alive"]:
                c = cells[u["cell"]]
                scores[u["player"]] += c["beacon"]
                u["energy"] = min(u["max_energy"], u["energy"] + c["recharge"])

    survivors = sorted((u for u in units.values() if u["alive"]), key=lambda u: u["id"])
    ranks = {}
    for player in spec["players"]:
        owned = [u for u in survivors if u["player"] == player]
        ranks[player] = (scores[player], len(owned), sum(u["health"] for u in owned))
    players = sorted(spec["players"])
    winner = None if ranks[players[0]] == ranks[players[1]] else max(players, key=lambda p: ranks[p])
    result = {
        "status": "complete",
        "selected": sorted(selected),
        "scores": [{"player": p, "score": scores[p]} for p in players],
        "units": [{k: u[k] for k in ["id", "player", "cell", "health", "energy"]} for u in survivors],
        "winner": winner,
    }
    return result, ranks


def expected_result(spec):
    rulings = {r["id"]: r for r in spec["rulings"]}
    docket_of = {rid: i for i, docket in enumerate(spec["dockets"]) for rid in docket}
    conflict = set()
    for r in spec["rulings"]:
        for other in r["conflicts"]:
            conflict.add(tuple(sorted((r["id"], other))))
    suffix = [0] * (len(spec["dockets"]) + 1)
    for i in range(len(spec["dockets"]) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + min(rulings[rid]["cost"] for rid in spec["dockets"][i])
    best = None

    def package_cost(ids, base_cost):
        chosen = set(ids)
        return base_cost + sum(
            row["cost"] for row in spec.get("coordination_costs", [])
            if all(rid in chosen for rid in row["rulings"])
        )

    def partial_valid(ids, depth):
        chosen = set(ids)
        for rid in ids:
            r = rulings[rid]
            if any(docket_of[x] < depth and x not in chosen for x in r["requires_all"]):
                return False
            for group in r["requires_any"]:
                if all(docket_of[x] < depth for x in group) and not chosen.intersection(group):
                    return False
        for requirement in spec.get("relay_requirements", []):
            count = sum(rid in chosen for rid in requirement["rulings"])
            future = {docket_of[rid] for rid in requirement["rulings"]
                      if rid not in chosen and docket_of[rid] >= depth}
            if count > requirement["max_selected"] or count + len(future) < requirement["min_selected"]:
                return False
        return True

    def visit(depth, ids, base_cost, slots):
        nonlocal best
        cost = package_cost(ids, base_cost)
        if cost + suffix[depth] > spec["budget"]:
            return
        if depth == len(spec["dockets"]):
            if not partial_valid(ids, depth):
                return
            result, ranks = replay(spec, set(ids))
            claimant = spec["claimant"]
            opponent = next(p for p in spec["players"] if p != claimant)
            outcome = 1 if result["winner"] is None else int(result["winner"] == claimant) * 2
            cr = ranks[claimant]
            quality = (outcome, cr[0], cr[1], cr[2], -ranks[opponent][0])
            selected_ids = tuple(sorted(ids))
            if (best is None or quality > best[0] or
                    (quality == best[0] and cost < best[1]) or
                    (quality == best[0] and cost == best[1] and selected_ids < best[2])):
                best = (quality, cost, selected_ids, result)
            return
        chosen = set(ids)
        for rid in spec["dockets"][depth]:
            r = rulings[rid]
            slot = (r["round"], r["unit"])
            if base_cost + r["cost"] > spec["budget"] or slot in slots:
                continue
            if any(tuple(sorted((rid, other))) in conflict for other in chosen):
                continue
            ids.append(rid)
            if partial_valid(ids, depth + 1):
                visit(depth + 1, ids, base_cost + r["cost"], slots | {slot})
            ids.pop()

    visit(0, [], 0, set())
    if best is None:
        return {"status": "infeasible", "selected": [], "scores": [], "units": [], "winner": None}
    return best[3]


def tiny_match(rounds=None):
    return {
        "players": ["amber", "violet"], "claimant": "amber", "budget": 0,
        "relay_requirements": [], "coordination_costs": [],
        "cells": [
            {"id": "a", "neighbors": ["b"], "move_cost": 1, "beacon": 1, "recharge": 1},
            {"id": "b", "neighbors": ["a"], "move_cost": 1, "beacon": 1, "recharge": 0},
        ],
        "units": [
            {"id": "one", "player": "amber", "cell": "a", "health": 5, "energy": 3, "max_energy": 4, "strength": 2},
            {"id": "two", "player": "violet", "cell": "b", "health": 5, "energy": 3, "max_energy": 4, "strength": 2},
        ],
        "rounds": rounds if rounds is not None else [[]], "rulings": [], "dockets": [],
    }


def ruling(rid, docket, action, cost=0, all_=None, any_=None, conflicts=None, round_=0, unit="one"):
    return {"id": rid, "cost": cost, "requires_all": all_ or [], "requires_any": any_ or [],
            "conflicts": conflicts or [], "round": round_, "unit": unit, "action": {"unit": unit, **action}, "docket": docket}


def generated(seed, count, width):
    rng = random.Random(seed)
    cells = []
    for i in range(6):
        cells.append({"id": f"c{i}", "neighbors": [f"c{(i - 1) % 6}", f"c{(i + 1) % 6}"],
                      "move_cost": 1 + (i + seed) % 2, "beacon": (i * 3 + seed) % 5,
                      "recharge": (i + seed) % 3})
    unit_rows = [
        ("a-sun", "amber", "c0", 10, 5, 3),
        ("a-ash", "amber", "c2", 8, 4, 2),
        ("v-moon", "violet", "c3", 10, 5, 3),
        ("v-mist", "violet", "c5", 8, 4, 2),
    ]
    units = [{"id": uid, "player": player, "cell": cell, "health": health,
              "energy": energy, "max_energy": 6, "strength": strength}
             for uid, player, cell, health, energy, strength in unit_rows]
    spec = {"players": ["amber", "violet"], "claimant": "amber", "budget": 0,
            "relay_requirements": [], "coordination_costs": [], "cells": cells, "units": units,
            "rounds": [[] for _ in range(count)], "rulings": [], "dockets": []}
    order = ["a-sun", "v-moon", "a-ash", "v-mist"]
    enemy = {"a-sun": "v-moon", "a-ash": "v-mist", "v-moon": "a-sun", "v-mist": "a-ash"}
    start_cell = {row[0]: row[2] for row in unit_rows}
    planted = [1 + rng.randrange(width - 1) for _ in range(count)]
    spec["rulings"], spec["dockets"] = [], []
    for d in range(count):
        ids = []
        for alt in range(width):
            rid = f"s{seed}-d{d:02d}-a{alt}"
            unit_id = order[d % len(order)]
            origin = int(start_cell[unit_id][1])
            action = ({"type": "wait"} if alt == 0 else {"type": "guard"} if alt == 1 else
                      {"type": "strike", "target": enemy[unit_id]} if alt == 2 else
                      {"type": "move", "to": f"c{(origin + (1 if d % 2 == 0 else -1)) % 6}"})
            r = ruling(rid, d, action, cost=(alt + d + seed) % 4, round_=d, unit=unit_id)
            if d and alt == planted[d]:
                prior = spec["dockets"][d - 1]
                r["requires_any"] = [[prior[planted[d - 1]], prior[(planted[d - 1] + 1) % width]]]
            elif d and alt == width - 1:
                prior = spec["dockets"][d - 1]
                r["requires_any"] = [[prior[0], prior[1]]]
            if d >= 3 and alt == planted[d] and d % 3 == 0:
                r["requires_all"] = [spec["dockets"][d - 3][planted[d - 3]]]
            if d >= 2 and alt != planted[d] and (d + alt + seed) % 3 == 0:
                r["conflicts"] = [spec["dockets"][d - 2][planted[d - 2]]]
            spec["rulings"].append({k: v for k, v in r.items() if k != "docket"})
            ids.append(rid)
        spec["dockets"].append(ids)
    even_members = []
    odd_members = []
    aggressive = []
    for d, docket in enumerate(spec["dockets"]):
        (even_members if d % 2 == 0 else odd_members).extend([docket[planted[d]], docket[(planted[d] + 1) % width]])
        aggressive.extend(docket[2:])
    spec["relay_requirements"] = [
        {"id": "even-links", "rulings": even_members, "min_selected": max(2, count // 3),
         "max_selected": (count + 1) // 2},
        {"id": "odd-links", "rulings": odd_members, "min_selected": max(2, count // 3),
         "max_selected": count // 2},
        {"id": "active-orders", "rulings": aggressive, "min_selected": 2,
         "max_selected": max(3, count - 2)},
    ]
    for start in range(0, count - 2, 3):
        row = [spec["dockets"][start + offset][planted[start + offset]] for offset in range(3)]
        spec["coordination_costs"].append({"rulings": row, "cost": 1 + (seed + start) % 3})
    spec["coordination_costs"].append({
        "rulings": [spec["dockets"][0][2], spec["dockets"][-1][2]], "cost": 3})
    planted_base = sum(next(r["cost"] for r in spec["rulings"] if r["id"] == spec["dockets"][d][planted[d]])
                       for d in range(count))
    planted_ids = {spec["dockets"][d][planted[d]] for d in range(count)}
    planted_extra = sum(row["cost"] for row in spec["coordination_costs"]
                        if set(row["rulings"]).issubset(planted_ids))
    spec["budget"] = planted_base + planted_extra
    return spec


def cases():
    public = json.loads(PUBLIC_BYTES)
    yield "public", public

    tie = tiny_match()
    tie["rulings"] = [
        {k: v for k, v in ruling("alpha", 0, {"type": "wait"}).items() if k != "docket"},
        {k: v for k, v in ruling("zeta", 0, {"type": "wait"}).items() if k != "docket"},
    ]
    tie["dockets"] = [["zeta", "alpha"]]
    yield "lexicographic-ruling-tie", tie

    cost_tie = tiny_match()
    cost_tie["budget"] = 1
    cost_tie["rulings"] = [
        {k: v for k, v in ruling("alpha-expensive", 0, {"type": "wait"}, cost=1).items() if k != "docket"},
        {k: v for k, v in ruling("zeta-cheap", 0, {"type": "wait"}).items() if k != "docket"},
    ]
    cost_tie["dockets"] = [["alpha-expensive", "zeta-cheap"]]
    yield "cost-before-id-tie-break", cost_tie

    survivor_rank = tiny_match([])
    survivor_rank["cells"].append({"id": "c", "neighbors": [], "move_cost": 1, "beacon": 0, "recharge": 0})
    for c in survivor_rank["cells"]:
        c["beacon"] = 0
        c["neighbors"] = []
    survivor_rank["units"] = [
        {"id": "amber-1", "player": "amber", "cell": "a", "health": 3, "energy": 0, "max_energy": 0, "strength": 1},
        {"id": "amber-2", "player": "amber", "cell": "b", "health": 3, "energy": 0, "max_energy": 0, "strength": 1},
        {"id": "violet-1", "player": "violet", "cell": "c", "health": 20, "energy": 0, "max_energy": 0, "strength": 1},
    ]
    yield "winner-survivor-count-before-health", survivor_rank

    health_rank = tiny_match([])
    for c in health_rank["cells"]:
        c["beacon"] = 0
    health_rank["units"][0]["health"] = 4
    health_rank["units"][1]["health"] = 5
    yield "winner-health-final-tie-break", health_rank

    impossible = tiny_match()
    impossible["rulings"] = [
        {k: v for k, v in ruling("need", 0, {"type": "wait"}, all_=["blocked"]).items() if k != "docket"},
        {k: v for k, v in ruling("blocked", 1, {"type": "wait"}, conflicts=["need"], unit="two").items() if k != "docket"},
    ]
    impossible["dockets"] = [["need"], ["blocked"]]
    yield "unsatisfiable-dependency-conflict", impossible

    narrow = tiny_match([[], []])
    narrow["budget"] = 2
    narrow["rulings"] = [
        {k: v for k, v in ruling("a-required", 0, {"type": "wait"}, all_=["b-link"]).items() if k != "docket"},
        {k: v for k, v in ruling("a-too-costly", 0, {"type": "guard"}, cost=3).items() if k != "docket"},
        {k: v for k, v in ruling("b-dead", 1, {"type": "wait"}, unit="two").items() if k != "docket"},
        {k: v for k, v in ruling("b-link", 1, {"type": "guard"}, cost=1, any_=[["c-blocked", "c-only"]], unit="two").items() if k != "docket"},
        {k: v for k, v in ruling("c-blocked", 2, {"type": "wait"}, conflicts=["a-required"], round_=1).items() if k != "docket"},
        {k: v for k, v in ruling("c-only", 2, {"type": "guard"}, cost=1, round_=1).items() if k != "docket"},
    ]
    narrow["dockets"] = [["a-required", "a-too-costly"], ["b-dead", "b-link"], ["c-blocked", "c-only"]]
    yield "near-unsatisfiable-exact-budget", narrow

    collision = tiny_match()
    collision["budget"] = 2
    collision["rulings"] = [
        {k: v for k, v in ruling("same-a", 0, {"type": "guard"}).items() if k != "docket"},
        {k: v for k, v in ruling("same-b", 1, {"type": "strike", "target": "two"}).items() if k != "docket"},
        {k: v for k, v in ruling("other-b", 1, {"type": "guard"}, unit="two").items() if k != "docket"},
    ]
    collision["dockets"] = [["same-a"], ["same-b", "other-b"]]
    yield "slot-collision-alternative", collision

    quorum = tiny_match([[], [], []])
    quorum["budget"] = 3
    quorum["rulings"] = []
    quorum["dockets"] = []
    for d in range(3):
        plain = ruling(f"plain-{d}", d, {"type": "wait"}, round_=d)
        linked = ruling(f"linked-{d}", d, {"type": "guard"}, cost=1, round_=d)
        quorum["rulings"].extend([{k: v for k, v in row.items() if k != "docket"} for row in [plain, linked]])
        quorum["dockets"].append([f"plain-{d}", f"linked-{d}"])
    quorum["relay_requirements"] = [
        {"id": "two-links", "rulings": ["linked-0", "linked-1", "linked-2"],
         "min_selected": 2, "max_selected": 2}
    ]
    yield "relay-quorum-forces-coupled-choice", quorum

    surcharge = tiny_match([[], []])
    surcharge["budget"] = 2
    surcharge["rulings"] = [
        {k: v for k, v in ruling("a", 0, {"type": "guard"}, cost=1).items() if k != "docket"},
        {k: v for k, v in ruling("a-safe", 0, {"type": "wait"}).items() if k != "docket"},
        {k: v for k, v in ruling("b", 1, {"type": "guard"}, cost=1, round_=1).items() if k != "docket"},
        {k: v for k, v in ruling("b-safe", 1, {"type": "wait"}, round_=1).items() if k != "docket"},
    ]
    surcharge["dockets"] = [["a", "a-safe"], ["b", "b-safe"]]
    surcharge["relay_requirements"] = [
        {"id": "one-active", "rulings": ["a", "b"], "min_selected": 1, "max_selected": 2}
    ]
    surcharge["coordination_costs"] = [{"rulings": ["a", "b"], "cost": 2}]
    yield "coordination-surcharge-breaks-base-budget", surcharge

    coordination_tie = tiny_match([[], []])
    coordination_tie["budget"] = 2
    coordination_tie["rulings"] = [
        {k: v for k, v in ruling("alpha-base-free", 0, {"type": "wait"}).items() if k != "docket"},
        {k: v for k, v in ruling("zeta-base-one", 0, {"type": "wait"}, cost=1).items() if k != "docket"},
        {k: v for k, v in ruling("anchor", 1, {"type": "wait"}, round_=1).items() if k != "docket"},
    ]
    coordination_tie["dockets"] = [["alpha-base-free", "zeta-base-one"], ["anchor"]]
    coordination_tie["coordination_costs"] = [
        {"rulings": ["alpha-base-free", "anchor"], "cost": 2}
    ]
    yield "coordination-cost-before-id-tie-break", coordination_tie

    cycle = tiny_match([])
    cycle["cells"] = [
        {"id": "a", "neighbors": ["b", "d"], "move_cost": 1, "beacon": 0, "recharge": 0},
        {"id": "b", "neighbors": ["a", "c"], "move_cost": 1, "beacon": 1, "recharge": 0},
        {"id": "c", "neighbors": ["b", "d"], "move_cost": 1, "beacon": 2, "recharge": 0},
        {"id": "d", "neighbors": ["c", "a"], "move_cost": 1, "beacon": 3, "recharge": 0},
    ]
    cycle["units"] = [
        {"id": "a1", "player": "amber", "cell": "a", "health": 5, "energy": 2, "max_energy": 2, "strength": 2},
        {"id": "a2", "player": "amber", "cell": "c", "health": 5, "energy": 2, "max_energy": 2, "strength": 2},
        {"id": "v1", "player": "violet", "cell": "b", "health": 5, "energy": 2, "max_energy": 2, "strength": 2},
        {"id": "v2", "player": "violet", "cell": "d", "health": 5, "energy": 2, "max_energy": 2, "strength": 2},
    ]
    cycle["rounds"] = [[
        {"unit": "a1", "type": "move", "to": "b"}, {"unit": "v1", "type": "move", "to": "c"},
        {"unit": "a2", "type": "move", "to": "d"}, {"unit": "v2", "type": "move", "to": "a"},
    ]]
    yield "closed-movement-cycle", cycle

    for seed in [2718, 4409, 9917]:
        yield f"seeded-coupled-{seed}", generated(seed, 9, 4)
    yield "wide-budget-performance-trap", generated(8128, 12, 4)


def run_case(name, spec, timeout=10):
    encoded = json.dumps(spec, separators=(",", ":")).encode()
    INPUT.write_bytes(encoded)
    OUTPUT.unlink(missing_ok=True)
    env = os.environ.copy()
    env["PATH"] = "/no-helper-programs"
    completed = subprocess.run([str(BINARY)], capture_output=True, text=True, timeout=timeout, env=env)
    assert completed.returncode == 0, f"{name}: {completed.stderr}"
    assert INPUT.read_bytes() == encoded, f"{name}: input modified"
    actual = json.loads(OUTPUT.read_text())
    assert list(actual) == OUTPUT_KEYS, f"{name}: wrong output keys/order"
    assert all(list(x) == ["player", "score"] for x in actual["scores"])
    assert all(list(x) == ["id", "player", "cell", "health", "energy"] for x in actual["units"])
    expected = expected_result(spec)
    assert actual == expected, f"{name}: incorrect\nactual={actual}\nexpected={expected}"


def run_named_case(target):
    try:
        for name, spec in cases():
            if name == target:
                run_case(name, spec)
                return
        raise AssertionError(f"missing verifier case: {target}")
    finally:
        INPUT.write_bytes(PUBLIC_BYTES)


def test_native_artifact_and_public_integrity():
    """Require Go source, an executable native ELF, and the unchanged public match."""
    assert SOURCE.is_file() and "package main" in SOURCE.read_text()
    assert BINARY.is_file() and BINARY.stat().st_mode & 0o111
    assert BINARY.read_bytes()[:4] == b"\x7fELF"
    assert hashlib.sha256(PUBLIC_BYTES).hexdigest() == PUBLIC_SHA256


def test_public_match():
    """Adjudicate the public match using the complete selection and replay contract."""
    run_named_case("public")


def test_lexicographic_ruling_tie():
    """Choose the lexicographically smallest sorted ruling IDs after all other ties."""
    run_named_case("lexicographic-ruling-tie")


def test_cost_precedes_id_tie_break():
    """Prefer lower base package cost before comparing selected ruling IDs."""
    run_named_case("cost-before-id-tie-break")


def test_winner_uses_survivor_count_before_health():
    """Break equal-score player rankings by survivor count before surviving health."""
    run_named_case("winner-survivor-count-before-health")


def test_winner_uses_health_as_final_tie_break():
    """Use total surviving health as the final player-ranking component."""
    run_named_case("winner-health-final-tie-break")


def test_unsatisfiable_dependency_conflict():
    """Report infeasible when a mandatory dependency conflicts with its requiring ruling."""
    run_named_case("unsatisfiable-dependency-conflict")


def test_near_unsatisfiable_exact_budget():
    """Find the sole dependency-compatible package that exactly consumes the budget."""
    run_named_case("near-unsatisfiable-exact-budget")


def test_slot_collision_uses_valid_alternative():
    """Reject duplicate round-unit patches while retaining a valid docket alternative."""
    run_named_case("slot-collision-alternative")


def test_relay_quorum_forces_coupled_choice():
    """Enforce both minimum and maximum counts for a global relay requirement."""
    run_named_case("relay-quorum-forces-coupled-choice")


def test_coordination_surcharge_breaks_base_budget():
    """Include an activated coordination surcharge when checking budget feasibility."""
    run_named_case("coordination-surcharge-breaks-base-budget")


def test_coordination_cost_precedes_id_tie_break():
    """Minimize total package cost, including surcharges, before lexicographic IDs."""
    run_named_case("coordination-cost-before-id-tie-break")


def test_closed_movement_cycle():
    """Resolve a collision-free closed movement cycle simultaneously and successfully."""
    run_named_case("closed-movement-cycle")


def test_seeded_coupled_2718():
    """Solve seed 2718 with coupled quorums, dependencies, conflicts, and replay effects."""
    run_named_case("seeded-coupled-2718")


def test_seeded_coupled_4409():
    """Solve seed 4409 with a different deterministic coupled constraint topology."""
    run_named_case("seeded-coupled-4409")


def test_seeded_coupled_9917():
    """Solve seed 9917 under deterministic budget pressure and action interactions."""
    run_named_case("seeded-coupled-9917")


def test_wide_budget_performance():
    """Solve the wide twelve-docket frontier without scanning every replay package."""
    run_named_case("wide-budget-performance-trap")


def test_reloads_changed_match():
    """Re-read match.json on every invocation instead of caching the public fixture."""
    first = json.loads(PUBLIC_BYTES)
    second = copy.deepcopy(first)
    second["budget"] = 0
    try:
        run_case("reload-first", first)
        run_case("reload-second", second)
    finally:
        INPUT.write_bytes(PUBLIC_BYTES)
