import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest


WORKSPACE = pathlib.Path("/workspace")
TASK_FILE = WORKSPACE / "task_file"
INPUT_PATH = TASK_FILE / "colony.json"
OUTPUT_PATH = WORKSPACE / "colony_plan.json"
BINARY_PATH = None
PUBLIC_SHA256 = "7a7c03b2a3ff14e82d5f9281d333f05c0220243f49bf24fa4f75bcd6e3476fdc"
NOBODY_UID = 65534
NOBODY_GID = 65534


def public_case():
    return {
        "case_id": "shackleton-eclipse-drill",
        "ruleset": "selene-2",
        "population": 2,
        "regolith": "volatile",
        "recycler": "water",
        "allow_emergency": True,
        "capacities": {
            "battery": 12,
            "oxygen": 18,
            "water": 18,
            "morale": 12,
            "hull": 12,
            "wear": 8,
            "fatigue": 7,
        },
        "initial": {
            "battery": 8,
            "oxygen": 18,
            "water": 18,
            "morale": 10,
            "dust": 3,
            "hull": 12,
            "wear": 1,
            "insight": 0,
            "fatigue": 1,
        },
        "targets": {"insight": 6, "hull": 6, "morale": 3},
        "sols": [
            {"id": "landing-check", "sunlight": 7, "hazard": "none"},
            {"id": "rim-flare", "sunlight": 5, "hazard": "flare"},
            {"id": "dark-crossing", "sunlight": 0, "hazard": "impact"},
            {"id": "fault-motion", "sunlight": 3, "hazard": "quake"},
            {"id": "sunrise-window", "sunlight": 8, "hazard": "none"},
            {"id": "return-flare", "sunlight": 6, "hazard": "flare"},
        ],
    }


def variant(case_id, **changes):
    case = copy.deepcopy(public_case())
    case["case_id"] = case_id
    for name, value in changes.items():
        case[name] = value
    return case


CAP_MEDIUM = {
    "battery": 12,
    "oxygen": 18,
    "water": 18,
    "morale": 12,
    "hull": 12,
    "wear": 8,
    "fatigue": 7,
}


INITIAL_MEDIUM = {
    "battery": 7,
    "oxygen": 16,
    "water": 15,
    "morale": 9,
    "dust": 5,
    "hull": 10,
    "wear": 1,
    "insight": 0,
    "fatigue": 1,
}


def sols(specs):
    return [
        {"id": f"s{index}-{hazard}", "sunlight": sunlight, "hazard": hazard}
        for index, (sunlight, hazard) in enumerate(specs, 1)
    ]


CASES = {
    "public": public_case(),
    "legacy_dust": variant(
        "legacy-dust-loss",
        ruleset="selene-1",
        population=1,
        regolith="dry",
        recycler="off",
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial=copy.deepcopy(INITIAL_MEDIUM),
        targets={"insight": 3, "hull": 5, "morale": 3},
        sols=sols([(8, "none"), (4, "impact"), (8, "none"), (2, "none")]),
    ),
    "modern_dust": variant(
        "modern-dust-credit",
        ruleset="selene-2",
        population=1,
        regolith="dry",
        recycler="off",
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial=copy.deepcopy(INITIAL_MEDIUM),
        targets={"insight": 3, "hull": 5, "morale": 3},
        sols=sols([(8, "none"), (4, "impact"), (8, "none"), (2, "none")]),
    ),
    "dry_mining": variant(
        "dry-mass-driver",
        population=2,
        regolith="dry",
        recycler="water",
        initial={**INITIAL_MEDIUM, "water": 9, "oxygen": 18, "dust": 2},
        targets={"insight": 3, "hull": 5, "morale": 3},
        sols=sols([(7, "none"), (6, "flare"), (1, "none"), (7, "quake"), (8, "none")]),
    ),
    "volatile_mining": variant(
        "volatile-wear-window",
        population=2,
        regolith="volatile",
        recycler="oxygen",
        initial={**INITIAL_MEDIUM, "water": 8, "oxygen": 12, "dust": 2, "wear": 3},
        targets={"insight": 3, "hull": 5, "morale": 2},
        sols=sols([(8, "none"), (5, "quake"), (0, "impact"), (8, "none"), (7, "flare")]),
    ),
    "recycler_off": variant(
        "recycler-offline",
        population=2,
        regolith="dry",
        recycler="off",
        initial={**INITIAL_MEDIUM, "oxygen": 15, "water": 13, "dust": 1},
        targets={"insight": 3, "hull": 4, "morale": 2},
        sols=sols([(7, "none"), (4, "flare"), (2, "impact"), (8, "none"), (6, "none")]),
    ),
    "hazard_conflict": variant(
        "south-wall-hazard-chain",
        population=1,
        regolith="volatile",
        recycler="water",
        initial={**INITIAL_MEDIUM, "hull": 8, "wear": 3, "oxygen": 14},
        targets={"insight": 3, "hull": 5, "morale": 3},
        sols=sols([(6, "flare"), (5, "impact"), (3, "quake"), (7, "impact"), (6, "none")]),
    ),
    "fatigue_bound": variant(
        "crew-redline",
        population=1,
        regolith="dry",
        recycler="oxygen",
        allow_emergency=False,
        capacities={**CAP_MEDIUM, "fatigue": 4},
        initial={**INITIAL_MEDIUM, "fatigue": 3, "dust": 2},
        targets={"insight": 6, "hull": 4, "morale": 2},
        sols=sols([(7, "none"), (4, "flare"), (7, "none"), (3, "impact"), (8, "none")]),
    ),
    "no_emergency": variant(
        "charter-no-emergency",
        population=2,
        regolith="volatile",
        recycler="water",
        allow_emergency=False,
        initial={**INITIAL_MEDIUM, "oxygen": 16, "water": 14, "dust": 2},
        targets={"insight": 3, "hull": 4, "morale": 2},
        sols=sols([(7, "none"), (4, "flare"), (0, "none"), (8, "impact"), (7, "none")]),
    ),
    "emergency_enabled": variant(
        "emergency-authority",
        population=3,
        regolith="volatile",
        recycler="oxygen",
        allow_emergency=True,
        capacities={**CAP_MEDIUM, "oxygen": 22, "water": 22, "wear": 1, "fatigue": 8},
        initial={**INITIAL_MEDIUM, "oxygen": 22, "water": 8, "morale": 11, "dust": 1, "wear": 1, "fatigue": 0},
        targets={"insight": 3, "hull": 4, "morale": 2},
        sols=sols([(5, "flare"), (0, "none"), (6, "none")]),
    ),
    "tie_break": variant(
        "complete-plan-key",
        population=1,
        regolith="dry",
        recycler="off",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial={**INITIAL_MEDIUM, "battery": 2, "oxygen": 18, "water": 18, "morale": 12, "dust": 0, "hull": 12},
        targets={"insight": 3, "hull": 0, "morale": 0},
        sols=sols([(0, "none"), (0, "none")]),
    ),
    "empty_feasible": variant(
        "handover-complete",
        targets={"insight": 0, "hull": 8, "morale": 8},
        sols=[],
    ),
    "empty_impossible": variant(
        "handover-incomplete",
        targets={"insight": 1, "hull": 8, "morale": 8},
        sols=[],
    ),
    "all_paths_impossible": variant(
        "sealed-failure",
        population=4,
        recycler="off",
        allow_emergency=False,
        initial={**INITIAL_MEDIUM, "oxygen": 2, "water": 2, "battery": 0},
        targets={"insight": 0, "hull": 0, "morale": 0},
        sols=sols([(0, "flare")]),
    ),
    "sweep_directive": variant(
        "legacy-array-sweep",
        ruleset="selene-1",
        population=1,
        regolith="dry",
        recycler="off",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial={**INITIAL_MEDIUM, "battery": 1, "oxygen": 12, "water": 12, "morale": 10, "dust": 4, "hull": 10, "wear": 0, "fatigue": 0},
        targets={"insight": 3, "hull": 1, "morale": 1},
        sols=sols([(0, "none"), (6, "none")]),
    ),
    "service_directive": variant(
        "extractor-service-closeout",
        ruleset="selene-2",
        population=1,
        regolith="dry",
        recycler="off",
        allow_emergency=False,
        capacities={**CAP_MEDIUM, "wear": 3},
        initial={**INITIAL_MEDIUM, "battery": 5, "oxygen": 8, "water": 2, "morale": 8, "dust": 0, "hull": 8, "wear": 3, "fatigue": 0},
        targets={"insight": 0, "hull": 1, "morale": 1},
        sols=sols([(0, "none"), (0, "none")]),
    ),
    "patch_directive": variant(
        "pressure-shell-closeout",
        ruleset="selene-2",
        population=1,
        regolith="dry",
        recycler="off",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial={**INITIAL_MEDIUM, "battery": 3, "oxygen": 10, "water": 10, "morale": 10, "dust": 0, "hull": 2, "wear": 0, "fatigue": 0},
        targets={"insight": 0, "hull": 1, "morale": 1},
        sols=sols([(0, "none")]),
    ),
    "hard_interaction": variant(
        "peary-long-night",
        ruleset="selene-1",
        population=2,
        regolith="volatile",
        recycler="oxygen",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_MEDIUM),
        initial={**INITIAL_MEDIUM, "battery": 9, "oxygen": 18, "water": 18, "morale": 11, "hull": 11, "dust": 4, "wear": 2},
        targets={"insight": 6, "hull": 6, "morale": 3},
        sols=sols([(9, "none"), (5, "flare"), (1, "impact"), (0, "quake"), (8, "none")]),
    ),
}


def matrix_case(
    case_id,
    *,
    ruleset,
    population,
    regolith,
    recycler,
    allow_emergency,
    capacities,
    initial,
    targets,
    sol_specs,
):
    return {
        "case_id": case_id,
        "ruleset": ruleset,
        "population": population,
        "regolith": regolith,
        "recycler": recycler,
        "allow_emergency": allow_emergency,
        "capacities": capacities,
        "initial": initial,
        "targets": targets,
        "sols": sols(sol_specs),
    }


CAP_LARGE = {
    "battery": 16,
    "oxygen": 24,
    "water": 24,
    "morale": 14,
    "hull": 14,
    "wear": 10,
    "fatigue": 9,
}


GENERATED_CASES = {
    "resource_crossover": matrix_case(
        "resource-crossover",
        ruleset="selene-2",
        population=2,
        regolith="volatile",
        recycler="water",
        allow_emergency=True,
        capacities=copy.deepcopy(CAP_LARGE),
        initial={
            "battery": 10,
            "oxygen": 22,
            "water": 18,
            "morale": 12,
            "dust": 6,
            "hull": 11,
            "wear": 4,
            "insight": 0,
            "fatigue": 2,
        },
        targets={"insight": 6, "hull": 6, "morale": 4},
        sol_specs=[
            (9, "none"),
            (2, "flare"),
            (0, "impact"),
            (6, "quake"),
        ],
    ),
    "legacy_dust_service_trap": matrix_case(
        "legacy-dust-service-trap",
        ruleset="selene-1",
        population=1,
        regolith="dry",
        recycler="off",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_LARGE),
        initial={
            "battery": 8,
            "oxygen": 20,
            "water": 18,
            "morale": 11,
            "dust": 7,
            "hull": 12,
            "wear": 2,
            "insight": 0,
            "fatigue": 1,
        },
        targets={"insight": 6, "hull": 5, "morale": 4},
        sol_specs=[
            (10, "none"),
            (1, "impact"),
            (8, "flare"),
            (0, "none"),
        ],
    ),
    "emergency_late_bind": matrix_case(
        "emergency-late-bind",
        ruleset="selene-2",
        population=4,
        regolith="volatile",
        recycler="oxygen",
        allow_emergency=True,
        capacities={
            **CAP_LARGE,
            "oxygen": 30,
            "water": 30,
            "wear": 8,
            "fatigue": 10,
        },
        initial={
            "battery": 12,
            "oxygen": 30,
            "water": 16,
            "morale": 13,
            "dust": 2,
            "hull": 12,
            "wear": 2,
            "insight": 0,
            "fatigue": 0,
        },
        targets={"insight": 6, "hull": 4, "morale": 2},
        sol_specs=[
            (5, "flare"),
            (0, "none"),
            (7, "quake"),
            (4, "flare"),
        ],
    ),
    "brace_patch_research_conflict": matrix_case(
        "brace-patch-research-conflict",
        ruleset="selene-2",
        population=2,
        regolith="dry",
        recycler="water",
        allow_emergency=False,
        capacities=copy.deepcopy(CAP_LARGE),
        initial={
            "battery": 9,
            "oxygen": 18,
            "water": 17,
            "morale": 12,
            "dust": 3,
            "hull": 6,
            "wear": 1,
            "insight": 0,
            "fatigue": 2,
        },
        targets={"insight": 6, "hull": 7, "morale": 5},
        sol_specs=[
            (7, "impact"),
            (6, "flare"),
            (1, "quake"),
            (8, "none"),
        ],
    ),
    "ruleset_split_same_weather": matrix_case(
        "ruleset-split-same-weather",
        ruleset="selene-1",
        population=3,
        regolith="volatile",
        recycler="water",
        allow_emergency=True,
        capacities={
            **CAP_LARGE,
            "oxygen": 28,
            "water": 28,
            "fatigue": 11,
        },
        initial={
            "battery": 11,
            "oxygen": 26,
            "water": 20,
            "morale": 13,
            "dust": 5,
            "hull": 13,
            "wear": 1,
            "insight": 0,
            "fatigue": 1,
        },
        targets={"insight": 6, "hull": 5, "morale": 3},
        sol_specs=[
            (9, "none"),
            (3, "quake"),
            (6, "flare"),
            (0, "impact"),
        ],
    ),
    "tight_wear_volatile": matrix_case(
        "tight-wear-volatile",
        ruleset="selene-2",
        population=1,
        regolith="volatile",
        recycler="oxygen",
        allow_emergency=False,
        capacities={
            **CAP_LARGE,
            "wear": 5,
            "fatigue": 6,
        },
        initial={
            "battery": 7,
            "oxygen": 14,
            "water": 7,
            "morale": 10,
            "dust": 4,
            "hull": 9,
            "wear": 4,
            "insight": 0,
            "fatigue": 1,
        },
        targets={"insight": 3, "hull": 3, "morale": 2},
        sol_specs=[
            (8, "none"),
            (5, "quake"),
            (0, "none"),
            (6, "impact"),
        ],
    ),
}


EXPECTED = {
    "public": {
        "minimum_safety": 5,
        "final_insight": 6,
        "final_morale": 5,
        "final_reserves": 24,
        "final_wear": 3,
        "emergency_sols": 0,
        "plan_key": "conserve:research,conserve:brace,conserve:research,conserve:rest,full:electrolyze,conserve:rest",
    },
    "legacy_dust": {
        "minimum_safety": 9,
        "final_insight": 6,
        "final_morale": 12,
        "final_reserves": 25,
        "final_wear": 3,
        "emergency_sols": 0,
        "plan_key": "full:research,conserve:brace,full:mine,full:research",
    },
    "modern_dust": {
        "minimum_safety": 9,
        "final_insight": 6,
        "final_morale": 12,
        "final_reserves": 27,
        "final_wear": 3,
        "emergency_sols": 0,
        "plan_key": "full:research,conserve:brace,full:mine,full:research",
    },
    "dry_mining": {
        "minimum_safety": 5,
        "final_insight": 3,
        "final_morale": 11,
        "final_reserves": 20,
        "final_wear": 7,
        "emergency_sols": 0,
        "plan_key": "conserve:mine,conserve:mine,full:rest,full:electrolyze,full:research",
    },
    "volatile_mining": {
        "minimum_safety": 2,
        "final_insight": 3,
        "final_morale": 5,
        "final_reserves": 16,
        "final_wear": 6,
        "emergency_sols": 0,
        "plan_key": "conserve:mine,conserve:brace,conserve:rest,conserve:research,full:rest",
    },
    "recycler_off": {
        "minimum_safety": 4,
        "final_insight": 3,
        "final_morale": 4,
        "final_reserves": 23,
        "final_wear": 3,
        "emergency_sols": 0,
        "plan_key": "conserve:mine,conserve:brace,conserve:rest,conserve:research,conserve:rest",
    },
    "hazard_conflict": {
        "minimum_safety": 4,
        "final_insight": 3,
        "final_morale": 12,
        "final_reserves": 19,
        "final_wear": 3,
        "emergency_sols": 0,
        "plan_key": "conserve:brace,full:brace,full:brace,full:brace,full:research",
    },
    "fatigue_bound": {
        "minimum_safety": 6,
        "final_insight": 6,
        "final_morale": 8,
        "final_reserves": 24,
        "final_wear": 1,
        "emergency_sols": 0,
        "plan_key": "conserve:rest,full:research,conserve:rest,conserve:research,full:rest",
    },
    "no_emergency": {
        "minimum_safety": 6,
        "final_insight": 3,
        "final_morale": 10,
        "final_reserves": 23,
        "final_wear": 4,
        "emergency_sols": 0,
        "plan_key": "conserve:mine,conserve:brace,conserve:rest,full:electrolyze,full:research",
    },
    "emergency_enabled": {
        "minimum_safety": 1,
        "final_insight": 3,
        "final_morale": 2,
        "final_reserves": 28,
        "final_wear": 1,
        "emergency_sols": 3,
        "plan_key": "emergency:brace,emergency:research,emergency:rest",
    },
    "tie_break": {
        "minimum_safety": 12,
        "final_insight": 3,
        "final_morale": 12,
        "final_reserves": 27,
        "final_wear": 1,
        "emergency_sols": 0,
        "plan_key": "full:research,full:rest",
    },
    "empty_feasible": {
        "minimum_safety": 10,
        "final_insight": 0,
        "final_morale": 10,
        "final_reserves": 44,
        "final_wear": 1,
        "emergency_sols": 0,
        "plan_key": "",
    },
    "empty_impossible": None,
    "all_paths_impossible": None,
    "sweep_directive": {
        "minimum_safety": 8,
        "final_insight": 3,
        "final_morale": 11,
        "final_reserves": 19,
        "final_wear": 0,
        "emergency_sols": 0,
        "plan_key": "conserve:sweep,full:research",
    },
    "service_directive": {
        "minimum_safety": 1,
        "final_insight": 0,
        "final_morale": 9,
        "final_reserves": 9,
        "final_wear": 2,
        "emergency_sols": 0,
        "plan_key": "conserve:service,full:mine",
    },
    "patch_directive": {
        "minimum_safety": 5,
        "final_insight": 0,
        "final_morale": 12,
        "final_reserves": 16,
        "final_wear": 0,
        "emergency_sols": 0,
        "plan_key": "full:patch",
    },
    "hard_interaction": {
        "minimum_safety": 6,
        "final_insight": 6,
        "final_morale": 10,
        "final_reserves": 24,
        "final_wear": 5,
        "emergency_sols": 0,
        "plan_key": "conserve:research,conserve:research,conserve:rest,full:brace,full:mine",
    },
}


STATE_FIELDS = {
    "battery",
    "oxygen",
    "water",
    "morale",
    "dust",
    "hull",
    "wear",
    "insight",
    "fatigue",
}


STATE_ORDER = (
    "battery",
    "oxygen",
    "water",
    "morale",
    "dust",
    "hull",
    "wear",
    "insight",
    "fatigue",
)

DIRECTIVES = (
    "rest",
    "sweep",
    "mine",
    "electrolyze",
    "service",
    "patch",
    "brace",
    "research",
)


def state_key(state):
    return tuple(state[name] for name in STATE_ORDER)


def state_from_key(key):
    return dict(zip(STATE_ORDER, key, strict=True))


def cap_add(state, field, amount, capacity):
    added = min(amount, capacity - state[field])
    state[field] += added
    return added, amount - added


def replay(case, plan_key):
    tokens = [] if plan_key == "" else plan_key.split(",")
    assert len(tokens) == len(case["sols"])
    state = copy.deepcopy(case["initial"])
    decisions = []
    ledger = []
    safety_values = []
    emergency_count = 0
    capacities = case["capacities"]
    for index, (sol, token) in enumerate(zip(case["sols"], tokens), 1):
        ration, directive_name = token.split(":")
        start = copy.deepcopy(state)
        dust_penalty = state["dust"]
        if case["ruleset"] == "selene-2":
            dust_penalty = (state["dust"] + 1) // 2
        raw = max(0, sol["sunlight"] - dust_penalty)
        solar_added, solar_spill = cap_add(state, "battery", raw, capacities["battery"])
        directive = {
            "battery_spent": 0,
            "oxygen_added": 0,
            "water_spent": 0,
            "water_added": 0,
            "hull_added": 0,
            "dust_removed": 0,
            "wear_delta": 0,
            "insight_added": 0,
            "fatigue_delta": 0,
        }
        apply_directive(case, state, directive_name, directive)
        hazard = {"oxygen_spent": 0, "hull_lost": 0, "morale_lost": 0, "wear_added": 0}
        braced = directive_name == "brace"
        apply_hazard(state, sol["hazard"], braced, hazard)
        ration_flow = {"oxygen_spent": 0, "water_spent": 0, "morale_delta": 0, "fatigue_added": 0}
        apply_ration(case, state, ration, ration_flow)
        recycle = {"resource": case["recycler"], "added": 0, "spill": 0}
        amount = case["population"] // 2
        if case["recycler"] in {"oxygen", "water"}:
            recycle["added"], recycle["spill"] = cap_add(
                state,
                case["recycler"],
                amount,
                capacities[case["recycler"]],
            )
        hazard_result = "none"
        if sol["hazard"] != "none":
            hazard_result = ("braced_" if braced else "open_") + sol["hazard"]
        decisions.append(
            {
                "sol": index,
                "id": sol["id"],
                "ration": ration,
                "directive": directive_name,
                "hazard_result": hazard_result,
            }
        )
        ledger.append(
            {
                "sol": index,
                "start": start,
                "solar": {"raw": raw, "added": solar_added, "spill": solar_spill},
                "directive": directive,
                "hazard": hazard,
                "ration": ration_flow,
                "recycle": recycle,
                "end": copy.deepcopy(state),
            }
        )
        safety_values.append(min(state[name] for name in ("oxygen", "water", "morale", "hull")))
        emergency_count += ration == "emergency"
    minimum_safety = min(safety_values) if safety_values else min(
        state[name] for name in ("oxygen", "water", "morale", "hull")
    )
    objective = {
        "minimum_safety": minimum_safety,
        "final_insight": state["insight"],
        "final_morale": state["morale"],
        "final_reserves": state["battery"] + state["oxygen"] + state["water"],
        "final_wear": state["wear"],
        "emergency_sols": emergency_count,
        "plan_key": plan_key,
    }
    return {
        "status": "feasible",
        "ruleset": case["ruleset"],
        "decisions": decisions,
        "ledger": ledger,
        "objective": objective,
    }


def maybe_spend(state, field, amount):
    if state[field] < amount:
        return False
    state[field] -= amount
    return True


def try_directive(case, state, name):
    capacities = case["capacities"]
    flow = {
        "battery_spent": 0,
        "oxygen_added": 0,
        "water_spent": 0,
        "water_added": 0,
        "hull_added": 0,
        "dust_removed": 0,
        "wear_delta": 0,
        "insight_added": 0,
        "fatigue_delta": 0,
    }
    fatigue = 0
    old_fatigue = state["fatigue"]
    if name == "rest":
        fatigue = -2
    elif name == "sweep":
        if state["dust"] <= 0 or not maybe_spend(state, "battery", 1):
            return None
        flow["battery_spent"] = 1
        amount = 2 if case["ruleset"] == "selene-1" else 3
        flow["dust_removed"] = min(amount, state["dust"])
        state["dust"] -= flow["dust_removed"]
        fatigue = 1
    elif name == "mine":
        wear, water = (2, 5) if case["regolith"] == "dry" else (3, 7)
        if state["wear"] + wear > capacities["wear"]:
            return None
        if not maybe_spend(state, "battery", 3):
            return None
        flow["battery_spent"] = 3
        state["wear"] += wear
        flow["wear_delta"] = wear
        flow["water_added"], _ = cap_add(state, "water", water, capacities["water"])
        fatigue = 2
    elif name == "electrolyze":
        if state["battery"] < 3 or state["water"] < 2:
            return None
        maybe_spend(state, "battery", 3)
        maybe_spend(state, "water", 2)
        flow["battery_spent"] = 3
        flow["water_spent"] = 2
        flow["oxygen_added"], _ = cap_add(state, "oxygen", 6, capacities["oxygen"])
        fatigue = 1
    elif name == "service":
        if state["wear"] <= 0 or not maybe_spend(state, "battery", 2):
            return None
        flow["battery_spent"] = 2
        removed = min(3, state["wear"])
        state["wear"] -= removed
        flow["wear_delta"] = -removed
        fatigue = 1
    elif name == "patch":
        if state["hull"] >= capacities["hull"]:
            return None
        if not maybe_spend(state, "battery", 3):
            return None
        flow["battery_spent"] = 3
        flow["hull_added"], _ = cap_add(state, "hull", 3, capacities["hull"])
        fatigue = 2
    elif name == "brace":
        if not maybe_spend(state, "battery", 1):
            return None
        flow["battery_spent"] = 1
        fatigue = 1
    elif name == "research":
        if state["battery"] < 2 or state["water"] < 1:
            return None
        maybe_spend(state, "battery", 2)
        maybe_spend(state, "water", 1)
        flow["battery_spent"] = 2
        flow["water_spent"] = 1
        state["insight"] += 3
        flow["insight_added"] = 3
        fatigue = 1
    else:
        return None
    state["fatigue"] = max(0, state["fatigue"] + fatigue)
    flow["fatigue_delta"] = state["fatigue"] - old_fatigue
    return flow


def try_hazard(state, name, braced):
    flow = {"oxygen_spent": 0, "hull_lost": 0, "morale_lost": 0, "wear_added": 0}
    if name == "none":
        return flow
    if name == "flare":
        amount = 1 if braced else 3
        if not maybe_spend(state, "oxygen", amount):
            return None
        flow["oxygen_spent"] = amount
        if not braced:
            flow["morale_lost"] = min(2, state["morale"])
            state["morale"] -= flow["morale_lost"]
    elif name == "impact":
        amount = 1 if braced else 4
        flow["hull_lost"] = min(amount, state["hull"])
        state["hull"] -= flow["hull_lost"]
    elif name == "quake":
        amount = 1 if braced else 2
        flow["hull_lost"] = min(amount, state["hull"])
        state["hull"] -= flow["hull_lost"]
        if not braced:
            flow["wear_added"] = 2
            state["wear"] += 2
    if state["hull"] <= 0 or state["morale"] <= 0:
        return None
    return flow


def try_ration(case, state, name):
    population = case["population"]
    flow = {"oxygen_spent": 0, "water_spent": 0, "morale_delta": 0, "fatigue_added": 0}
    if name == "full":
        flow["oxygen_spent"] = 2 * population
        flow["water_spent"] = 2 * population
        morale = 2
    elif name == "conserve":
        flow["oxygen_spent"] = population
        flow["water_spent"] = population
        flow["fatigue_added"] = 1
        morale = -1
    elif name == "emergency" and case["allow_emergency"]:
        flow["oxygen_spent"] = population
        flow["water_spent"] = (population + 1) // 2
        flow["fatigue_added"] = 2
        morale = -3
    else:
        return None
    if not maybe_spend(state, "oxygen", flow["oxygen_spent"]):
        return None
    if not maybe_spend(state, "water", flow["water_spent"]):
        return None
    old_morale = state["morale"]
    state["morale"] = max(0, min(case["capacities"]["morale"], state["morale"] + morale))
    flow["morale_delta"] = state["morale"] - old_morale
    state["fatigue"] += flow["fatigue_added"]
    if state["morale"] <= 0:
        return None
    return flow


def try_recycle(case, state):
    flow = {"resource": case["recycler"], "added": 0, "spill": 0}
    if case["recycler"] in {"oxygen", "water"}:
        amount = case["population"] // 2
        flow["added"], flow["spill"] = cap_add(
            state,
            case["recycler"],
            amount,
            case["capacities"][case["recycler"]],
        )
    return flow


def is_valid_end(case, state):
    capacities = case["capacities"]
    return (
        0 <= state["battery"] <= capacities["battery"]
        and 0 < state["oxygen"] <= capacities["oxygen"]
        and 0 < state["water"] <= capacities["water"]
        and 0 < state["morale"] <= capacities["morale"]
        and state["dust"] >= 0
        and 0 < state["hull"] <= capacities["hull"]
        and 0 <= state["wear"] <= capacities["wear"]
        and state["insight"] >= 0
        and 0 <= state["fatigue"] <= capacities["fatigue"]
    )


def try_transition(case, start, sol, ration, directive_name):
    state = copy.deepcopy(start)
    dust_penalty = state["dust"]
    if case["ruleset"] == "selene-2":
        dust_penalty = (state["dust"] + 1) // 2
    raw = max(0, sol["sunlight"] - dust_penalty)
    cap_add(state, "battery", raw, case["capacities"]["battery"])
    if try_directive(case, state, directive_name) is None:
        return None
    if try_hazard(state, sol["hazard"], directive_name == "brace") is None:
        return None
    if try_ration(case, state, ration) is None:
        return None
    try_recycle(case, state)
    if not is_valid_end(case, state):
        return None
    return state


def objective_key(record):
    state = state_from_key(record["state_key"])
    return (
        record["minimum_safety"],
        state["insight"],
        state["morale"],
        state["battery"] + state["oxygen"] + state["water"],
        -state["wear"],
        -record["emergencies"],
        record["plan_key"],
    )


def better_record(candidate, incumbent):
    if incumbent is None:
        return True
    candidate_key = objective_key(candidate)
    incumbent_key = objective_key(incumbent)
    if candidate_key[:-1] != incumbent_key[:-1]:
        return candidate_key[:-1] > incumbent_key[:-1]
    return candidate_key[-1] < incumbent_key[-1]


def retained(records, candidate):
    for record in records:
        if (
            record["minimum_safety"] >= candidate["minimum_safety"]
            and record["emergencies"] <= candidate["emergencies"]
            and record["plan_key"] <= candidate["plan_key"]
        ):
            return records
    result = []
    for record in records:
        if (
            candidate["minimum_safety"] >= record["minimum_safety"]
            and candidate["emergencies"] <= record["emergencies"]
            and candidate["plan_key"] <= record["plan_key"]
        ):
            continue
        result.append(record)
    result.append(candidate)
    return result


def solve_reference(case):
    initial_key = state_key(case["initial"])
    initial_safety = min(case["initial"][name] for name in ("oxygen", "water", "morale", "hull"))
    minimum_safety = 31
    if not case["sols"]:
        minimum_safety = initial_safety
    records = {
        initial_key: [
            {
                "state_key": initial_key,
                "minimum_safety": minimum_safety,
                "emergencies": 0,
                "plan_key": "",
            }
        ]
    }
    for sol in case["sols"]:
        next_records = {}
        for variants in records.values():
            for record in variants:
                start = state_from_key(record["state_key"])
                rations = ["full", "conserve"]
                if case["allow_emergency"]:
                    rations.append("emergency")
                for ration in rations:
                    for directive_name in DIRECTIVES:
                        state = try_transition(case, start, sol, ration, directive_name)
                        if state is None:
                            continue
                        token = f"{ration}:{directive_name}"
                        plan_key = token
                        if record["plan_key"]:
                            plan_key = f"{record['plan_key']},{token}"
                        safety = min(state[name] for name in ("oxygen", "water", "morale", "hull"))
                        candidate_key = state_key(state)
                        candidate = {
                            "state_key": candidate_key,
                            "minimum_safety": min(record["minimum_safety"], safety),
                            "emergencies": record["emergencies"] + int(ration == "emergency"),
                            "plan_key": plan_key,
                        }
                        bucket = next_records.setdefault(candidate_key, [])
                        next_records[candidate_key] = retained(bucket, candidate)
        records = next_records
    best = None
    for variants in records.values():
        for record in variants:
            state = state_from_key(record["state_key"])
            if state["insight"] < case["targets"]["insight"]:
                continue
            if state["hull"] < case["targets"]["hull"]:
                continue
            if state["morale"] < case["targets"]["morale"]:
                continue
            if better_record(record, best):
                best = record
    if best is None:
        return None
    state = state_from_key(best["state_key"])
    return {
        "minimum_safety": best["minimum_safety"],
        "final_insight": state["insight"],
        "final_morale": state["morale"],
        "final_reserves": state["battery"] + state["oxygen"] + state["water"],
        "final_wear": state["wear"],
        "emergency_sols": best["emergencies"],
        "plan_key": best["plan_key"],
    }


def brute_force_reference(case):
    best = None
    rations = ["full", "conserve"]
    if case["allow_emergency"]:
        rations.append("emergency")
    choices = [(ration, directive_name) for ration in rations for directive_name in DIRECTIVES]

    def visit(index, state, minimum_safety, emergencies, tokens):
        nonlocal best
        if index == len(case["sols"]):
            if state["insight"] < case["targets"]["insight"]:
                return
            if state["hull"] < case["targets"]["hull"]:
                return
            if state["morale"] < case["targets"]["morale"]:
                return
            key = state_key(state)
            plan_key = ",".join(tokens)
            candidate = {
                "state_key": key,
                "minimum_safety": minimum_safety,
                "emergencies": emergencies,
                "plan_key": plan_key,
            }
            if better_record(candidate, best):
                best = candidate
            return
        sol = case["sols"][index]
        for ration, directive_name in choices:
            updated = try_transition(case, state, sol, ration, directive_name)
            if updated is None:
                continue
            safety = min(updated[name] for name in ("oxygen", "water", "morale", "hull"))
            visit(
                index + 1,
                updated,
                min(minimum_safety, safety),
                emergencies + int(ration == "emergency"),
                [*tokens, f"{ration}:{directive_name}"],
            )

    initial_minimum = 31
    if not case["sols"]:
        initial_minimum = min(case["initial"][name] for name in ("oxygen", "water", "morale", "hull"))
    visit(0, copy.deepcopy(case["initial"]), initial_minimum, 0, [])
    if best is None:
        return None
    state = state_from_key(best["state_key"])
    return {
        "minimum_safety": best["minimum_safety"],
        "final_insight": state["insight"],
        "final_morale": state["morale"],
        "final_reserves": state["battery"] + state["oxygen"] + state["water"],
        "final_wear": state["wear"],
        "emergency_sols": best["emergencies"],
        "plan_key": best["plan_key"],
    }


def expected_by_oracle(case):
    expected = solve_reference(case)
    if expected is None:
        return {
            "status": "impossible",
            "ruleset": case["ruleset"],
            "decisions": [],
            "ledger": [],
            "objective": None,
        }
    result = replay(case, expected["plan_key"])
    assert result["objective"] == expected
    return result


def spend(state, field, amount):
    assert state[field] >= amount
    state[field] -= amount


def apply_directive(case, state, name, flow):
    capacities = case["capacities"]
    old_fatigue = state["fatigue"]
    fatigue = 0
    if name == "rest":
        fatigue = -2
    elif name == "sweep":
        assert state["dust"] > 0
        spend(state, "battery", 1)
        flow["battery_spent"] = 1
        amount = 2 if case["ruleset"] == "selene-1" else 3
        flow["dust_removed"] = min(amount, state["dust"])
        state["dust"] -= flow["dust_removed"]
        fatigue = 1
    elif name == "mine":
        spend(state, "battery", 3)
        flow["battery_spent"] = 3
        wear, water = (2, 5) if case["regolith"] == "dry" else (3, 7)
        state["wear"] += wear
        flow["wear_delta"] = wear
        flow["water_added"], _ = cap_add(state, "water", water, capacities["water"])
        fatigue = 2
    elif name == "electrolyze":
        spend(state, "battery", 3)
        spend(state, "water", 2)
        flow["battery_spent"] = 3
        flow["water_spent"] = 2
        flow["oxygen_added"], _ = cap_add(state, "oxygen", 6, capacities["oxygen"])
        fatigue = 1
    elif name == "service":
        assert state["wear"] > 0
        spend(state, "battery", 2)
        flow["battery_spent"] = 2
        removed = min(3, state["wear"])
        state["wear"] -= removed
        flow["wear_delta"] = -removed
        fatigue = 1
    elif name == "patch":
        assert state["hull"] < capacities["hull"]
        spend(state, "battery", 3)
        flow["battery_spent"] = 3
        flow["hull_added"], _ = cap_add(state, "hull", 3, capacities["hull"])
        fatigue = 2
    elif name == "brace":
        spend(state, "battery", 1)
        flow["battery_spent"] = 1
        fatigue = 1
    elif name == "research":
        spend(state, "battery", 2)
        spend(state, "water", 1)
        flow["battery_spent"] = 2
        flow["water_spent"] = 1
        flow["insight_added"] = 3
        state["insight"] += 3
        fatigue = 1
    state["fatigue"] = max(0, state["fatigue"] + fatigue)
    flow["fatigue_delta"] = state["fatigue"] - old_fatigue


def apply_hazard(state, name, braced, flow):
    if name == "flare":
        amount = 1 if braced else 3
        spend(state, "oxygen", amount)
        flow["oxygen_spent"] = amount
        if not braced:
            flow["morale_lost"] = min(2, state["morale"])
            state["morale"] -= flow["morale_lost"]
    elif name == "impact":
        amount = 1 if braced else 4
        flow["hull_lost"] = min(amount, state["hull"])
        state["hull"] -= flow["hull_lost"]
    elif name == "quake":
        amount = 1 if braced else 2
        flow["hull_lost"] = min(amount, state["hull"])
        state["hull"] -= flow["hull_lost"]
        if not braced:
            flow["wear_added"] = 2
            state["wear"] += 2


def apply_ration(case, state, name, flow):
    population = case["population"]
    if name == "full":
        flow["oxygen_spent"] = 2 * population
        flow["water_spent"] = 2 * population
        morale = 2
    elif name == "conserve":
        flow["oxygen_spent"] = population
        flow["water_spent"] = population
        flow["fatigue_added"] = 1
        morale = -1
    else:
        flow["oxygen_spent"] = population
        flow["water_spent"] = (population + 1) // 2
        flow["fatigue_added"] = 2
        morale = -3
    spend(state, "oxygen", flow["oxygen_spent"])
    spend(state, "water", flow["water_spent"])
    old_morale = state["morale"]
    state["morale"] = max(0, min(case["capacities"]["morale"], state["morale"] + morale))
    flow["morale_delta"] = state["morale"] - old_morale
    state["fatigue"] += flow["fatigue_added"]


def expected_output(name):
    expected = EXPECTED[name]
    if expected is None:
        case = CASES[name]
        return {
            "status": "impossible",
            "ruleset": case["ruleset"],
            "decisions": [],
            "ledger": [],
            "objective": None,
        }
    result = replay(CASES[name], expected["plan_key"])
    assert result["objective"] == expected
    return result


@pytest.fixture(scope="session", autouse=True)
def compiled_planner(tmp_path_factory):
    global BINARY_PATH

    source = TASK_FILE / "main.go"
    assert source.is_file(), "missing required Go source /workspace/task_file/main.go"
    BINARY_PATH = tmp_path_factory.mktemp("colony-build") / "planner"
    env = os.environ.copy()
    env["CGO_ENABLED"] = "0"
    subprocess.run(
        ["/usr/local/go/bin/go", "build", "-o", str(BINARY_PATH), str(source)],
        cwd=WORKSPACE,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="session", autouse=True)
def restore_public_input():
    original = INPUT_PATH.read_bytes()
    yield
    INPUT_PATH.write_bytes(original)
    OUTPUT_PATH.unlink(missing_ok=True)


def invoke(case):
    input_text = json.dumps(case, separators=(",", ":")) + "\n"
    completed, raw = run_isolated(input_text)
    assert completed.returncode == 0, completed.stderr
    assert raw is not None, "planner did not create /workspace/colony_plan.json"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        pytest.fail(f"invalid output JSON: {error}")
    return parsed, raw


def run_isolated(input_text, timeout=90, stale_output=False):
    assert BINARY_PATH is not None
    with tempfile.TemporaryDirectory(prefix="colony-planner-") as root_name:
        root = pathlib.Path(root_name)
        workspace = root / "workspace"
        task_file = workspace / "task_file"
        tmp = root / "tmp"
        task_file.mkdir(parents=True)
        tmp.mkdir()
        os.chmod(root, 0o755)
        shutil.copy2(BINARY_PATH, root / "planner")
        os.chmod(root / "planner", 0o755)
        os.chmod(workspace, 0o777)
        os.chmod(task_file, 0o755)
        os.chmod(tmp, 0o1777)
        shutil.copy2(TASK_FILE / "CHARTER_SPEC.md", task_file / "CHARTER_SPEC.md")
        shutil.copy2(TASK_FILE / "go.mod", task_file / "go.mod")
        shutil.copy2(TASK_FILE / "main.go", task_file / "main.go")
        (task_file / "colony.json").write_text(input_text, encoding="utf-8")
        if stale_output:
            (workspace / "colony_plan.json").write_text(
                '{"stale":true}\n',
                encoding="utf-8",
            )

        def isolate_child():
            os.chroot(root)
            os.chdir("/workspace")
            os.setgroups([])
            os.setgid(NOBODY_GID)
            os.setuid(NOBODY_UID)

        completed = subprocess.run(
            ["/planner"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            preexec_fn=isolate_child,
        )
        output = workspace / "colony_plan.json"
        raw = output.read_bytes() if output.exists() else None
        return completed, raw


def assert_case(name):
    actual, _ = invoke(CASES[name])
    assert actual == expected_output(name)


def test_input_integrity_and_go_artifact():
    assert hashlib.sha256(INPUT_PATH.read_bytes()).hexdigest() == PUBLIC_SHA256
    source = (TASK_FILE / "main.go").read_text(encoding="utf-8")
    assert "package main" in source


def test_launch_schema_public_and_rerun():
    first, first_raw = invoke(CASES["public"])
    second, second_raw = invoke(CASES["public"])
    assert first_raw == second_raw
    assert first == expected_output("public")
    assert set(first) == {"status", "ruleset", "decisions", "ledger", "objective"}
    assert len(first["decisions"]) == len(CASES["public"]["sols"])
    assert len(first["ledger"]) == len(CASES["public"]["sols"])
    for row in first["ledger"]:
        assert set(row["start"]) == STATE_FIELDS
        assert set(row["end"]) == STATE_FIELDS


def test_ruleset_and_delayed_dust_interaction():
    assert_case("legacy_dust")
    assert_case("modern_dust")


def test_regolith_and_recycler_compatibility_matrix():
    assert_case("dry_mining")
    assert_case("volatile_mining")
    assert_case("recycler_off")


def test_hazard_resource_and_wear_conflicts():
    assert_case("hazard_conflict")
    assert_case("no_emergency")
    assert_case("emergency_enabled")


def test_fatigue_target_and_complete_plan_tie_breaks():
    assert_case("fatigue_bound")
    assert_case("tie_break")


def test_empty_and_impossible_campaigns():
    assert_case("empty_feasible")
    assert_case("empty_impossible")
    assert_case("all_paths_impossible")


def test_all_directive_families_and_phase_accounting():
    assert_case("sweep_directive")
    assert_case("service_directive")
    assert_case("patch_directive")


def test_hard_multi_rule_campaign_and_derived_ledger():
    assert_case("hard_interaction")


def test_reference_oracle_matches_bruteforce_on_tiny_cases():
    tiny_cases = {
        "tie_break": CASES["tie_break"],
        "sweep_directive": CASES["sweep_directive"],
        "patch_directive": CASES["patch_directive"],
        "all_paths_impossible": CASES["all_paths_impossible"],
    }
    for name, case in tiny_cases.items():
        assert solve_reference(case) == brute_force_reference(case), name


def test_generated_compatibility_matrix_from_oracle():
    feasible_count = 0
    public_plan = EXPECTED["public"]["plan_key"]
    for name, case in GENERATED_CASES.items():
        expected = expected_by_oracle(case)
        actual, _ = invoke(case)
        assert actual == expected, name
        if expected["status"] == "feasible":
            feasible_count += 1
            assert expected["objective"]["plan_key"] != public_plan
            assert len(expected["decisions"]) >= 4
    assert feasible_count >= 5


def test_malformed_input_removes_stale_output():
    malformed_inputs = []
    malformed_inputs.append('{"case_id":"bad","case_id":"duplicate"}\n')

    missing = copy.deepcopy(CASES["tie_break"])
    del missing["allow_emergency"]
    malformed_inputs.append(json.dumps(missing) + "\n")

    unknown = copy.deepcopy(CASES["tie_break"])
    unknown["unexpected"] = True
    malformed_inputs.append(json.dumps(unknown) + "\n")

    wrong_type = copy.deepcopy(CASES["tie_break"])
    wrong_type["population"] = "1"
    malformed_inputs.append(json.dumps(wrong_type) + "\n")

    out_of_range = copy.deepcopy(CASES["tie_break"])
    out_of_range["capacities"]["battery"] = 31
    malformed_inputs.append(json.dumps(out_of_range) + "\n")

    duplicate_sol = copy.deepcopy(CASES["tie_break"])
    duplicate_sol["sols"][1]["id"] = duplicate_sol["sols"][0]["id"]
    malformed_inputs.append(json.dumps(duplicate_sol) + "\n")

    too_many_sols = copy.deepcopy(CASES["tie_break"])
    too_many_sols["sols"] = sols([(0, "none")] * 11)
    malformed_inputs.append(json.dumps(too_many_sols) + "\n")

    trailing = json.dumps(CASES["tie_break"]) + "\n{}\n"
    malformed_inputs.append(trailing)

    for malformed in malformed_inputs:
        completed, raw = run_isolated(malformed, timeout=20, stale_output=True)
        assert completed.returncode != 0
        assert raw is None
