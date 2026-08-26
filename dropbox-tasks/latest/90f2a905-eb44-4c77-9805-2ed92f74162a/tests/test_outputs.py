import os
import subprocess
from pathlib import Path

import pytest

APP_DIR = Path(os.environ.get("TASK_ENV", "/app/environment"))
BINARY_REL = Path("bin/parcel-access-gateway")
ROLES = [
    "ops",
    "finance",
    "carrier",
    "support",
    "admin",
    "auditor",
    "partner",
    "worker",
]
SCOPES = [
    "north",
    "south",
    "east",
    "west",
    "global",
    "retail",
    "wholesale",
    "intl",
    "archive",
    "priority",
    "standard",
    "field",
    "warehouse",
    "cold",
    "fragile",
    "bulk",
]
STATES = [
    "draft",
    "queued",
    "active",
    "settled",
    "paused",
    "closing",
    "replay",
    "audit",
]


def route_contract(route_id):
    mode = "STRICT"
    if 48 <= route_id <= 55 or 64 <= route_id <= 71:
        mode = "SCOPE_FLEX"
    if 56 <= route_id <= 63 or 72 <= route_id <= 79:
        mode = "STATE_FLEX"
    return {
        "actor": ROLES[route_id % len(ROLES)],
        "scope": SCOPES[(route_id * 3 + 1) % len(SCOPES)],
        "phase": STATES[(route_id * 5 + 2) % len(STATES)],
        "limit": 80 + (route_id % 9) * 15,
        "mode": mode,
    }


def other(values, current):
    for value in values:
        if value != current:
            return value
    raise AssertionError("no alternate value")


def expected_decision(route_id, actor, scope, phase, units, segment):
    rule = route_contract(route_id)
    if route_id < 0 or route_id > 127 or units < 0 or segment not in (0, 1):
        return None
    capacity = rule["limit"]
    if rule["mode"] == "STATE_FLEX" and segment:
        capacity *= 2
    if rule["mode"] != "STATE_FLEX" and segment:
        return "DENY"
    if units > capacity:
        return "DENY"
    if actor != rule["actor"]:
        return "DENY"
    if rule["mode"] == "SCOPE_FLEX":
        return "ALLOW" if scope == rule["scope"] else "DENY"
    if rule["mode"] == "STATE_FLEX":
        return "ALLOW" if phase == rule["phase"] else "DENY"
    return "ALLOW" if scope == rule["scope"] and phase == rule["phase"] else "DENY"


def expected_decision_with_rule(rule_id, actor, scope, phase, units, segment):
    return expected_decision(rule_id, actor, scope, phase, units, segment)


def allowed_request_fields(route_id, exact_boundary=False):
    rule = route_contract(route_id)
    actor = rule["actor"]
    scope = rule["scope"]
    phase = rule["phase"]
    segment = 0
    capacity = rule["limit"]
    if rule["mode"] == "SCOPE_FLEX":
        phase = other(STATES, rule["phase"])
    elif rule["mode"] == "STATE_FLEX":
        scope = other(SCOPES, rule["scope"])
        segment = 1
        capacity = rule["limit"] * 2
    units = capacity if exact_boundary else max(1, min(capacity, rule["limit"] // 2))
    return actor, scope, phase, units, segment, capacity


def req_record(request_id, route_id, actor, scope, phase, units, segment):
    return f"REQ {request_id} {route_id} {actor} {scope} {phase} {units} {segment}"


def pin_record(route_id, actor, scope, phase, units, segment):
    return f"PIN {route_id} {actor} {scope} {phase} {units} {segment}"


def hold_record(route_id, ttl, actor, scope, phase, units, segment):
    return f"HOLD {route_id} {ttl} {actor} {scope} {phase} {units} {segment}"


def map_record(route_id, source_route_id, ttl):
    return f"MAP {route_id} {source_route_id} {ttl}"


def pair_record(route_id, left_source_route_id, right_source_route_id, ttl):
    return f"PAIR {route_id} {left_source_route_id} {right_source_route_id} {ttl}"


def seal_record(route_id, ttl, actor, scope, phase, units, segment):
    return f"SEAL {route_id} {ttl} {actor} {scope} {phase} {units} {segment}"


def budget_record(route_id, ttl, max_units):
    return f"BUDGET {route_id} {ttl} {max_units}"


def lease_record(route_id, ttl, actor, max_units):
    return f"LEASE {route_id} {ttl} {actor} {max_units}"


def rate_record(route_id, ttl, max_allows):
    return f"RATE {route_id} {ttl} {max_allows}"


def run_script(binary_path, tmp_path, lines):
    script = tmp_path / "scenario.script"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = subprocess.run(
        [str(binary_path), str(script)],
        cwd=APP_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=True,
    )
    return result.stdout.splitlines()


@pytest.fixture(scope="session")
def binary_path():
    """The project must build through the documented Makefile interface."""
    subprocess.run(
        ["make", "clean"],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    result = subprocess.run(
        ["make", "test"],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    binary = APP_DIR / BINARY_REL
    assert binary.exists(), f"missing binary {binary}"
    return binary


def test_binary_handles_happy_script(binary_path, tmp_path):
    """A documented happy-path script should produce only allow decisions."""
    happy = (
        (APP_DIR / "testdata" / "happy.script").read_text(encoding="utf-8").splitlines()
    )
    lines = [line for line in happy if line and not line.startswith("#")]
    output = run_script(binary_path, tmp_path, lines)
    assert len(output) == len(lines)
    assert all(" ALLOW " in line for line in output)


def test_malformed_request_records_are_ignored(binary_path, tmp_path):
    """Malformed route, unit, segment, and trailing fields must be ignored."""
    strict = route_contract(0)
    state = route_contract(56)
    lines = [
        req_record(
            "negative_route",
            -1,
            strict["actor"],
            strict["scope"],
            strict["phase"],
            1,
            0,
        ),
        req_record(
            "high_route", 128, strict["actor"], strict["scope"], strict["phase"], 1, 0
        ),
        req_record(
            "bad_units", 0, strict["actor"], strict["scope"], strict["phase"], -1, 0
        ),
        req_record(
            "bad_segment_hi", 56, state["actor"], state["scope"], state["phase"], 1, 2
        ),
        req_record(
            "bad_segment_neg",
            56,
            state["actor"],
            state["scope"],
            state["phase"],
            1,
            -1,
        ),
        req_record(
            "trailing", 0, strict["actor"], strict["scope"], strict["phase"], 1, 0
        )
        + " extra",
        req_record(
            "good_after", 0, strict["actor"], strict["scope"], strict["phase"], 1, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == ["good_after ALLOW 0"]


def test_non_numeric_request_records_are_ignored(binary_path, tmp_path):
    """Non-numeric integer fields must be ignored without stopping the script."""
    strict = route_contract(0)
    lines = [
        req_record(
            "route_word",
            "abc",
            strict["actor"],
            strict["scope"],
            strict["phase"],
            1,
            0,
        ),
        req_record(
            "units_word",
            0,
            strict["actor"],
            strict["scope"],
            strict["phase"],
            "many",
            0,
        ),
        req_record(
            "segment_word",
            0,
            strict["actor"],
            strict["scope"],
            strict["phase"],
            1,
            "flag",
        ),
        req_record(
            "good_tail", 0, strict["actor"], strict["scope"], strict["phase"], 1, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == ["good_tail ALLOW 0"]


@pytest.mark.parametrize("route_id", [0, 47, 48, 55, 56, 63, 64, 71, 72, 79, 80, 127])
def test_route_capacity_exact_boundary_accepts_next_unit_rejects(
    binary_path, tmp_path, route_id
):
    """The exact route capacity boundary is accepted and the next unit is denied."""
    actor, scope, phase, units, segment, capacity = allowed_request_fields(
        route_id, exact_boundary=True
    )
    lines = [
        req_record(
            f"boundary_ok_{route_id:03d}",
            route_id,
            actor,
            scope,
            phase,
            units,
            segment,
        ),
        req_record(
            f"boundary_hi_{route_id:03d}",
            route_id,
            actor,
            scope,
            phase,
            capacity + 1,
            segment,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"boundary_ok_{route_id:03d} ALLOW {route_id}",
        f"boundary_hi_{route_id:03d} DENY {route_id}",
    ]


@pytest.mark.parametrize(
    "route_id,source_route",
    [(12, 56), (31, 64), (83, 72), (127, 48), (6, 80)],
)
def test_generated_overlay_quota_replay_variants_are_route_agnostic(
    binary_path, tmp_path, route_id, source_route
):
    """Generated overlay cases compose replay idempotency, rate, and budget state."""
    actor, scope, phase, units, segment, _ = allowed_request_fields(source_route)
    lines = [
        map_record(route_id, source_route, 4),
        lease_record(route_id, 4, actor, units),
        rate_record(route_id, 3, 1),
        budget_record(route_id, 4, units * 2),
        req_record(
            f"generatedReplay{route_id}",
            route_id,
            actor,
            scope,
            phase,
            units,
            segment,
        ),
        req_record(
            f"generatedReplay{route_id}",
            route_id,
            other(ROLES, actor),
            scope,
            phase,
            units,
            segment,
        ),
        req_record(
            f"generatedRateA{route_id}",
            route_id,
            actor,
            scope,
            phase,
            units,
            segment,
        ),
        req_record(
            f"generatedRateB{route_id}",
            route_id,
            actor,
            scope,
            phase,
            units,
            segment,
        ),
        req_record(
            f"generatedBudget{route_id}",
            route_id,
            actor,
            scope,
            phase,
            units,
            segment,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"generatedReplay{route_id} ALLOW {route_id}",
        f"generatedReplay{route_id} ALLOW {route_id}",
        f"generatedRateA{route_id} DENY {route_id}",
        f"generatedRateB{route_id} DENY {route_id}",
        f"generatedBudget{route_id} ALLOW {route_id}",
    ]


def test_invalid_request_record_is_not_entered_into_replay_ledger(
    binary_path, tmp_path
):
    """Ignored request records should not reserve an unsequenced replay key."""
    strict = route_contract(0)
    lines = [
        req_record(
            "parcelReplay",
            999,
            strict["actor"],
            strict["scope"],
            strict["phase"],
            1,
            0,
        ),
        req_record(
            "parcelReplay",
            0,
            strict["actor"],
            strict["scope"],
            strict["phase"],
            1,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == ["parcelReplay ALLOW 0"]


def test_duplicate_unsequenced_request_replays_original_decision(binary_path, tmp_path):
    """A duplicate unsequenced request id should replay the first result."""
    first = route_contract(0)
    second = route_contract(56)
    lines = [
        req_record(
            "parcelStable",
            0,
            first["actor"],
            first["scope"],
            first["phase"],
            1,
            0,
        ),
        req_record(
            "parcelStable",
            56,
            second["actor"],
            other(SCOPES, second["scope"]),
            second["phase"],
            second["limit"] + 8,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        "parcelStable ALLOW 0",
        "parcelStable ALLOW 0",
    ]


def test_replayed_unsequenced_request_does_not_age_or_spend_budget(
    binary_path, tmp_path
):
    """A replayed unsequenced request should not spend capacity or tick ttl state."""
    route_id = 0
    rule = route_contract(route_id)
    lines = [
        budget_record(route_id, 2, 1),
        req_record(
            "budgetReplay",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            1,
            0,
        ),
        req_record(
            "budgetReplay",
            route_id,
            other(ROLES, rule["actor"]),
            rule["scope"],
            rule["phase"],
            1,
            0,
        ),
        req_record(
            "budgetFresh",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            1,
            0,
        ),
        req_record(
            "budgetAfter",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            1,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budgetReplay ALLOW {route_id}",
        f"budgetReplay ALLOW {route_id}",
        f"budgetFresh DENY {route_id}",
        f"budgetAfter ALLOW {route_id}",
    ]


def test_replayed_unsequenced_denial_does_not_consume_pending_checkpoint(
    binary_path, tmp_path
):
    """A replayed unsequenced denial should not consume a later checkpoint."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 6
    lines = [
        req_record(
            "checkpointReplay",
            route_id,
            rule["actor"],
            rule["scope"],
            other(STATES, rule["phase"]),
            units,
            1,
        ),
        pin_record(route_id, rule["actor"], alt_scope, rule["phase"], units, 1),
        req_record(
            "checkpointReplay",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "checkpointFresh",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"checkpointReplay DENY {route_id}",
        f"checkpointReplay DENY {route_id}",
        f"checkpointFresh ALLOW {route_id}",
    ]


def test_pin_checkpoint_mismatch_denies_then_consumes(binary_path, tmp_path):
    """A pending route checkpoint should deny the first mismatching request only."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 7
    lines = [
        pin_record(route_id, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "pin_miss", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
        req_record(
            "pin_after", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pin_miss DENY {route_id}",
        f"pin_after ALLOW {route_id}",
    ]


def test_pin_checkpoint_exact_match_waits_across_other_routes(binary_path, tmp_path):
    """A checkpoint should wait until the next valid request for the same route."""
    route_id = 56
    other_route = 55
    rule = route_contract(route_id)
    other_rule = route_contract(other_route)
    units = rule["limit"] + 5
    other_units = max(1, other_rule["limit"] // 3)
    lines = [
        pin_record(route_id, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "unrelated",
            other_route,
            other_rule["actor"],
            other_rule["scope"],
            other_rule["phase"],
            other_units,
            0,
        ),
        req_record(
            "pin_exact",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"unrelated ALLOW {other_route}",
        f"pin_exact ALLOW {route_id}",
    ]


def test_pin_checkpoint_replacement_uses_latest_record(binary_path, tmp_path):
    """A later checkpoint for a route should replace the earlier one."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 9
    lines = [
        pin_record(route_id, rule["actor"], rule["scope"], rule["phase"], units, 1),
        pin_record(route_id, rule["actor"], alt_scope, rule["phase"], units, 1),
        req_record(
            "pin_latest", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"pin_latest ALLOW {route_id}"]


def test_pin_checkpoint_match_still_runs_normal_policy(binary_path, tmp_path):
    """A matching checkpoint must not override the route's normal denial logic."""
    route_id = 0
    rule = route_contract(route_id)
    units = rule["limit"] + 1
    lines = [
        pin_record(route_id, rule["actor"], rule["scope"], rule["phase"], units, 0),
        req_record(
            "pin_policy",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"pin_policy DENY {route_id}"]


def test_invalid_pin_records_are_ignored(binary_path, tmp_path):
    """Malformed checkpoint records should not affect later requests."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 3
    lines = [
        f"PIN {route_id} {rule['actor']} {rule['scope']} {rule['phase']} {units}",
        pin_record(999, rule["actor"], rule["scope"], rule["phase"], units, 1),
        pin_record(route_id, rule["actor"], rule["scope"], rule["phase"], units, 2),
        req_record(
            "pin_clean", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"pin_clean ALLOW {route_id}"]


def test_hold_checkpoint_survives_unrelated_request(binary_path, tmp_path):
    """A timed checkpoint should survive while its ttl remains positive."""
    route_id = 56
    other_route = 55
    rule = route_contract(route_id)
    other_rule = route_contract(other_route)
    units = rule["limit"] + 4
    other_units = max(1, other_rule["limit"] // 2)
    lines = [
        hold_record(route_id, 2, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "hold_other",
            other_route,
            other_rule["actor"],
            other_rule["scope"],
            other_rule["phase"],
            other_units,
            0,
        ),
        req_record(
            "hold_match",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_other ALLOW {other_route}",
        f"hold_match ALLOW {route_id}",
    ]


def test_hold_checkpoint_expires_after_ttl(binary_path, tmp_path):
    """A timed checkpoint should expire after enough other-route requests."""
    route_id = 56
    other_route = 55
    rule = route_contract(route_id)
    other_rule = route_contract(other_route)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 6
    lines = [
        hold_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "hold_tick",
            other_route,
            other_rule["actor"],
            other_rule["scope"],
            other_rule["phase"],
            max(1, other_rule["limit"] // 2),
            0,
        ),
        req_record(
            "hold_expired",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_tick ALLOW {other_route}",
        f"hold_expired ALLOW {route_id}",
    ]


def test_invalid_request_does_not_age_hold_ttl(binary_path, tmp_path):
    """Ignored request records should not age timed checkpoints."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 6
    lines = [
        hold_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "ignored_tick",
            999,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "hold_still_pending",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_still_pending DENY {route_id}"
    ]


def test_hold_checkpoint_mismatch_consumes(binary_path, tmp_path):
    """A timed checkpoint mismatch should deny once and then clear."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 8
    lines = [
        hold_record(route_id, 3, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "hold_miss",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "hold_after",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_miss DENY {route_id}",
        f"hold_after ALLOW {route_id}",
    ]


def test_hold_and_pin_replacements_share_route_slot(binary_path, tmp_path):
    """Later checkpoint records for a route should replace earlier ones."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 5
    lines = [
        pin_record(route_id, rule["actor"], alt_scope, rule["phase"], units, 1),
        hold_record(route_id, 2, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "hold_replaced",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            1,
        ),
        hold_record(route_id, 2, rule["actor"], rule["scope"], rule["phase"], units, 1),
        pin_record(route_id, rule["actor"], alt_scope, rule["phase"], units, 1),
        req_record(
            "pin_replaced",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_replaced ALLOW {route_id}",
        f"pin_replaced ALLOW {route_id}",
    ]


def test_invalid_hold_records_are_ignored(binary_path, tmp_path):
    """Malformed timed checkpoint records should not affect later requests."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 2
    lines = [
        f"HOLD {route_id} {rule['actor']} {rule['scope']} {rule['phase']} {units} 1",
        hold_record(999, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        hold_record(route_id, 0, rule["actor"], rule["scope"], rule["phase"], units, 1),
        hold_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 2),
        req_record(
            "hold_clean",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"hold_clean ALLOW {route_id}"]


def test_map_overlay_uses_source_rule_with_original_output_route(binary_path, tmp_path):
    """A route overlay should evaluate with the source rule but print route_id."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    units = source["limit"] + 4
    lines = [
        map_record(route_id, source_route, 2),
        req_record(
            "map_source",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        ),
    ]
    assert (
        expected_decision_with_rule(
            source_route,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        )
        == "ALLOW"
    )
    assert run_script(binary_path, tmp_path, lines) == [f"map_source ALLOW {route_id}"]


def test_map_overlay_rejects_destination_native_fields(binary_path, tmp_path):
    """An active overlay should not silently use the destination route rule."""
    route_id = 10
    source_route = 56
    destination = route_contract(route_id)
    lines = [
        map_record(route_id, source_route, 1),
        req_record(
            "map_dest",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"map_dest DENY {route_id}"]


def test_map_overlay_expires_after_ttl(binary_path, tmp_path):
    """A route overlay should expire after enough requests for that route."""
    route_id = 10
    source_route = 56
    destination = route_contract(route_id)
    source = route_contract(source_route)
    lines = [
        map_record(route_id, source_route, 1),
        req_record(
            "map_tick",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            source["limit"] + 4,
            1,
        ),
        req_record(
            "map_expired",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"map_tick ALLOW {route_id}",
        f"map_expired ALLOW {route_id}",
    ]


def test_map_overlay_replacement_uses_latest_source(binary_path, tmp_path):
    """A later overlay should replace the source route used by an earlier one."""
    route_id = 10
    stale_source = 56
    latest_source = 48
    latest = route_contract(latest_source)
    lines = [
        map_record(route_id, stale_source, 3),
        map_record(route_id, latest_source, 2),
        req_record(
            "map_latest",
            route_id,
            latest["actor"],
            latest["scope"],
            other(STATES, latest["phase"]),
            max(1, latest["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"map_latest ALLOW {route_id}"]


def test_map_overlay_runs_after_route_checkpoint(binary_path, tmp_path):
    """A route overlay should run only after a matching route checkpoint."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    alt_scope = other(SCOPES, source["scope"])
    units = source["limit"] + 7
    lines = [
        map_record(route_id, source_route, 3),
        pin_record(route_id, source["actor"], alt_scope, source["phase"], units, 1),
        req_record(
            "map_pin_match",
            route_id,
            source["actor"],
            alt_scope,
            source["phase"],
            units,
            1,
        ),
        pin_record(
            route_id, source["actor"], source["scope"], source["phase"], units, 1
        ),
        req_record(
            "map_pin_miss",
            route_id,
            source["actor"],
            alt_scope,
            source["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"map_pin_match ALLOW {route_id}",
        f"map_pin_miss DENY {route_id}",
    ]


def test_invalid_map_records_are_ignored(binary_path, tmp_path):
    """Malformed route overlay records should not affect later requests."""
    route_id = 10
    destination = route_contract(route_id)
    lines = [
        f"MAP {route_id} 56",
        map_record(999, 56, 1),
        map_record(route_id, 999, 1),
        map_record(route_id, 56, 0),
        req_record(
            "map_clean",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"map_clean ALLOW {route_id}"]


def test_map_overlay_follows_chained_source(binary_path, tmp_path):
    """A route overlay source may itself be another active overlay."""
    route_id = 10
    middle_route = 11
    source_route = 56
    source = route_contract(source_route)
    lines = [
        map_record(route_id, middle_route, 2),
        map_record(middle_route, source_route, 2),
        req_record(
            "map_chain",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            source["limit"] + 4,
            1,
        ),
        req_record(
            "map_source_still_active",
            middle_route,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            source["limit"] + 4,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"map_chain ALLOW {route_id}",
        f"map_source_still_active ALLOW {middle_route}",
    ]


def test_map_overlay_cycle_denies_request(binary_path, tmp_path):
    """A route overlay cycle should deny instead of recursing forever."""
    route_id = 10
    middle_route = 11
    rule = route_contract(route_id)
    lines = [
        map_record(route_id, middle_route, 2),
        map_record(middle_route, route_id, 2),
        req_record(
            "map_cycle",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            max(1, rule["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"map_cycle DENY {route_id}"]


def test_pair_overlay_requires_both_source_rules(binary_path, tmp_path):
    """A paired overlay should allow only when both source rules allow."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = min(left["limit"], right["limit"]) - 5
    lines = [
        pair_record(route_id, left_route, right_route, 2),
        req_record(
            "pair_allow",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "pair_deny",
            route_id,
            left["actor"],
            other(SCOPES, left["scope"]),
            right["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_allow ALLOW {route_id}",
        f"pair_deny DENY {route_id}",
    ]


def test_pair_overlay_expires_after_route_requests(binary_path, tmp_path):
    """A paired overlay should expire after requests for the overlaid route."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    destination = route_contract(route_id)
    lines = [
        pair_record(route_id, left_route, right_route, 1),
        req_record(
            "pair_tick",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            min(left["limit"], right["limit"]) - 5,
            0,
        ),
        req_record(
            "pair_expired",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_tick ALLOW {route_id}",
        f"pair_expired ALLOW {route_id}",
    ]


def test_pair_and_map_replacements_share_overlay_slot(binary_path, tmp_path):
    """Later overlay records for a route should replace earlier ones."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = min(left["limit"], right["limit"]) - 5
    lines = [
        map_record(route_id, 23, 3),
        pair_record(route_id, left_route, right_route, 2),
        req_record(
            "pair_replaced_map",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        pair_record(route_id, left_route, right_route, 2),
        map_record(route_id, left_route, 2),
        req_record(
            "map_replaced_pair",
            route_id,
            left["actor"],
            left["scope"],
            other(STATES, right["phase"]),
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_replaced_map ALLOW {route_id}",
        f"map_replaced_pair ALLOW {route_id}",
    ]


def test_pair_overlay_runs_after_route_checkpoint(binary_path, tmp_path):
    """A paired overlay should run only after matching route checkpoints."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = min(left["limit"], right["limit"]) - 5
    lines = [
        pair_record(route_id, left_route, right_route, 3),
        pin_record(route_id, left["actor"], left["scope"], right["phase"], units, 0),
        req_record(
            "pair_pin_match",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        pin_record(route_id, left["actor"], left["scope"], right["phase"], units, 0),
        req_record(
            "pair_pin_miss",
            route_id,
            left["actor"],
            other(SCOPES, left["scope"]),
            right["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_pin_match ALLOW {route_id}",
        f"pair_pin_miss DENY {route_id}",
    ]


def test_pair_overlay_resolves_source_overlay(binary_path, tmp_path):
    """A paired overlay source may resolve through another active overlay."""
    route_id = 10
    middle_route = 11
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    lines = [
        pair_record(route_id, left_route, middle_route, 2),
        map_record(middle_route, right_route, 2),
        req_record(
            "pair_chain",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            min(left["limit"], right["limit"]) - 5,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"pair_chain ALLOW {route_id}"]


def test_pair_overlay_does_not_age_source_overlay(binary_path, tmp_path):
    """A paired overlay should not spend ttl from source overlays it resolves."""
    route_id = 10
    source_overlay_route = 11
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = min(left["limit"], right["limit"]) - 5
    lines = [
        pair_record(route_id, left_route, source_overlay_route, 1),
        map_record(source_overlay_route, right_route, 1),
        req_record(
            "pair_parent",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "source_overlay_still_active",
            source_overlay_route,
            right["actor"],
            other(SCOPES, right["scope"]),
            right["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_parent ALLOW {route_id}",
        f"source_overlay_still_active ALLOW {source_overlay_route}",
    ]


def test_pair_overlay_cycle_through_source_denies(binary_path, tmp_path):
    """A paired overlay source cycle should deny the request."""
    route_id = 10
    source_overlay_route = 11
    left_route = 48
    left = route_contract(left_route)
    lines = [
        pair_record(route_id, left_route, source_overlay_route, 2),
        map_record(source_overlay_route, route_id, 2),
        req_record(
            "pair_source_cycle",
            route_id,
            left["actor"],
            left["scope"],
            left["phase"],
            max(1, left["limit"] // 3),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"pair_source_cycle DENY {route_id}"
    ]


def test_invalid_pair_records_are_ignored(binary_path, tmp_path):
    """Malformed paired overlay records should not affect later requests."""
    route_id = 10
    destination = route_contract(route_id)
    lines = [
        f"PAIR {route_id} 48 56",
        pair_record(999, 48, 56, 1),
        pair_record(route_id, 999, 56, 1),
        pair_record(route_id, 48, 999, 1),
        pair_record(route_id, 48, 56, 0),
        req_record(
            "pair_clean",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"pair_clean ALLOW {route_id}"]


def test_budget_limits_cumulative_allowed_units(binary_path, tmp_path):
    """A route budget should deny requests that exceed remaining units."""
    route_id = 10
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 5)
    lines = [
        budget_record(route_id, 3, units * 2),
        req_record(
            "budget_first",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "budget_second",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "budget_third",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_first ALLOW {route_id}",
        f"budget_second ALLOW {route_id}",
        f"budget_third DENY {route_id}",
    ]


def test_budget_denied_policy_does_not_spend_units(binary_path, tmp_path):
    """A route denial before budget evaluation should leave budget unchanged."""
    route_id = 10
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 4)
    lines = [
        budget_record(route_id, 2, units),
        req_record(
            "budget_policy_deny",
            route_id,
            other(ROLES, rule["actor"]),
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "budget_after_deny",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_policy_deny DENY {route_id}",
        f"budget_after_deny ALLOW {route_id}",
    ]


def test_budget_expires_after_ttl(binary_path, tmp_path):
    """A route budget should expire after enough requests for that route."""
    route_id = 10
    rule = route_contract(route_id)
    lines = [
        budget_record(route_id, 1, 1),
        req_record(
            "budget_tick",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            1,
            0,
        ),
        req_record(
            "budget_expired",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            2,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_tick ALLOW {route_id}",
        f"budget_expired ALLOW {route_id}",
    ]


def test_budget_applies_after_map_overlay(binary_path, tmp_path):
    """A budget should apply after an overlay allows a request."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    units = 4
    lines = [
        map_record(route_id, source_route, 2),
        budget_record(route_id, 2, units),
        req_record(
            "budget_map_first",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            0,
        ),
        req_record(
            "budget_map_second",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_map_first ALLOW {route_id}",
        f"budget_map_second DENY {route_id}",
    ]


def test_budget_applies_after_pair_overlay(binary_path, tmp_path):
    """A budget should apply after a paired overlay allows a request."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = 5
    lines = [
        pair_record(route_id, left_route, right_route, 2),
        budget_record(route_id, 2, units),
        req_record(
            "budget_pair_first",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "budget_pair_second",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_pair_first ALLOW {route_id}",
        f"budget_pair_second DENY {route_id}",
    ]


def test_invalid_budget_records_are_ignored(binary_path, tmp_path):
    """Malformed budget records should not affect later requests."""
    route_id = 10
    rule = route_contract(route_id)
    lines = [
        f"BUDGET {route_id} 2",
        budget_record(999, 1, 1),
        budget_record(route_id, 0, 1),
        budget_record(route_id, 1, -1),
        req_record(
            "budget_clean",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            max(1, rule["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"budget_clean ALLOW {route_id}"
    ]


def test_rate_limits_allowed_request_count_without_spending_on_denials(
    binary_path, tmp_path
):
    """Rate quotas spend only on allowed requests but age on every valid request."""
    route_id = 0
    rule = route_contract(route_id)
    bad_actor = other(ROLES, rule["actor"])
    lines = [
        rate_record(route_id, 4, 2),
        req_record(
            "first", route_id, rule["actor"], rule["scope"], rule["phase"], 1, 0
        ),
        req_record(
            "policy_miss", route_id, bad_actor, rule["scope"], rule["phase"], 1, 0
        ),
        req_record(
            "second", route_id, rule["actor"], rule["scope"], rule["phase"], 1, 0
        ),
        req_record(
            "quota_miss", route_id, rule["actor"], rule["scope"], rule["phase"], 1, 0
        ),
        req_record(
            "after_ttl", route_id, rule["actor"], rule["scope"], rule["phase"], 1, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"first ALLOW {route_id}",
        f"policy_miss DENY {route_id}",
        f"second ALLOW {route_id}",
        f"quota_miss DENY {route_id}",
        f"after_ttl ALLOW {route_id}",
    ]


def test_rate_applies_after_overlay_before_budget_spend(binary_path, tmp_path):
    """Rate denials after an overlay do not spend the route budget."""
    route_id = 80
    source_route_id = 0
    source = route_contract(source_route_id)
    lines = [
        map_record(route_id, source_route_id, 4),
        rate_record(route_id, 3, 1),
        budget_record(route_id, 4, 6),
        req_record(
            "first", route_id, source["actor"], source["scope"], source["phase"], 3, 0
        ),
        req_record(
            "rate_miss",
            route_id,
            source["actor"],
            source["scope"],
            source["phase"],
            3,
            0,
        ),
        req_record(
            "rate_last_tick",
            route_id,
            source["actor"],
            source["scope"],
            source["phase"],
            3,
            0,
        ),
        req_record(
            "rate_expired",
            route_id,
            source["actor"],
            source["scope"],
            source["phase"],
            3,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"first ALLOW {route_id}",
        f"rate_miss DENY {route_id}",
        f"rate_last_tick DENY {route_id}",
        f"rate_expired ALLOW {route_id}",
    ]


def test_invalid_rate_records_are_ignored(binary_path, tmp_path):
    """Invalid rate records must not create quota state."""
    route_id = 0
    rule = route_contract(route_id)
    lines = [
        "RATE -1 2 1",
        "RATE 0 0 1",
        "RATE 0 2 -1",
        "RATE 0 2 many",
        "RATE 0 2 0 extra",
        req_record(
            "valid", route_id, rule["actor"], rule["scope"], rule["phase"], 1, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"valid ALLOW {route_id}"]


def test_state_records_with_extra_fields_are_ignored(binary_path, tmp_path):
    """State records with trailing fields should not mutate gateway state."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 5
    lines = [
        f"PIN {route_id} {rule['actor']} {rule['scope']} {rule['phase']} {units} 1 extra",
        f"HOLD {route_id} 2 {rule['actor']} {rule['scope']} {rule['phase']} {units} 1 extra",
        f"MAP {route_id} 0 2 extra",
        f"PAIR {route_id} 48 0 2 extra",
        f"SEAL {route_id} 2 {rule['actor']} {rule['scope']} {rule['phase']} {units} 1 extra",
        f"BUDGET {route_id} 3 0 extra",
        f"LEASE {route_id} 3 {other(ROLES, rule['actor'])} 0 extra",
        f"RATE {route_id} 3 0 extra",
        req_record(
            "extra_state_fields",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"extra_state_fields ALLOW {route_id}"
    ]


def test_lease_limits_actor_and_units_before_policy(binary_path, tmp_path):
    """A route lease should enforce actor and per-request units."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 4
    high_units = rule["limit"] + 8
    lines = [
        lease_record(route_id, 3, rule["actor"], units),
        req_record(
            "lease_allow", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
        req_record(
            "lease_actor",
            route_id,
            other(ROLES, rule["actor"]),
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "lease_units",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            high_units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"lease_allow ALLOW {route_id}",
        f"lease_actor DENY {route_id}",
        f"lease_units DENY {route_id}",
    ]


def test_lease_denial_ages_and_expires(binary_path, tmp_path):
    """A lease denied request should age the lease ttl."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 6
    lines = [
        lease_record(route_id, 1, rule["actor"], 1),
        req_record(
            "lease_tick", route_id, rule["actor"], alt_scope, rule["phase"], units, 1
        ),
        req_record(
            "lease_expired",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"lease_tick DENY {route_id}",
        f"lease_expired ALLOW {route_id}",
    ]


def test_lease_applies_before_map_overlay(binary_path, tmp_path):
    """A lease should gate the original route before overlay resolution."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    destination = route_contract(route_id)
    units = source["limit"] + 4
    lines = [
        map_record(route_id, source_route, 2),
        lease_record(route_id, 2, destination["actor"], units),
        req_record(
            "lease_map",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        ),
    ]
    assert (
        expected_decision_with_rule(
            source_route,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        )
        == "ALLOW"
    )
    assert run_script(binary_path, tmp_path, lines) == [f"lease_map DENY {route_id}"]


def test_lease_denial_ages_overlay_ttl(binary_path, tmp_path):
    """A lease denial should still age an overlay on the original route."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    destination = route_contract(route_id)
    units = source["limit"] + 4
    lines = [
        map_record(route_id, source_route, 1),
        lease_record(route_id, 1, destination["actor"], units),
        req_record(
            "lease_overlay_tick",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        ),
        req_record(
            "overlay_after_lease",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"lease_overlay_tick DENY {route_id}",
        f"overlay_after_lease ALLOW {route_id}",
    ]


def test_lease_denial_ages_budget_ttl(binary_path, tmp_path):
    """A lease denial should still age a budget on the original route."""
    route_id = 56
    rule = route_contract(route_id)
    alt_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 4
    lines = [
        budget_record(route_id, 1, 1),
        lease_record(route_id, 1, rule["actor"], 1),
        req_record(
            "lease_budget_tick",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "budget_after_lease",
            route_id,
            rule["actor"],
            alt_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"lease_budget_tick DENY {route_id}",
        f"budget_after_lease ALLOW {route_id}",
    ]


def test_checkpoint_denial_ages_route_state(binary_path, tmp_path):
    """A checkpoint denial should still age route-scoped state."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    destination = route_contract(route_id)
    units = source["limit"] + 4
    lines = [
        map_record(route_id, source_route, 1),
        budget_record(route_id, 1, 1),
        lease_record(route_id, 1, source["actor"], units),
        pin_record(
            route_id, source["actor"], source["scope"], source["phase"], units, 1
        ),
        req_record(
            "checkpoint_state_tick",
            route_id,
            source["actor"],
            other(SCOPES, source["scope"]),
            source["phase"],
            units,
            1,
        ),
        req_record(
            "state_after_checkpoint",
            route_id,
            destination["actor"],
            destination["scope"],
            destination["phase"],
            max(1, destination["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"checkpoint_state_tick DENY {route_id}",
        f"state_after_checkpoint ALLOW {route_id}",
    ]


def test_composed_stateful_controls_age_and_fall_back_in_order(binary_path, tmp_path):
    """Checkpoint, lease, rate, budget, and overlay state must compose in order."""
    route_id = 10
    source_route = 56
    source = route_contract(source_route)
    units = source["limit"] + 4
    source_scope = other(SCOPES, source["scope"])
    wrong_actor = other(ROLES, source["actor"])
    lines = [
        map_record(route_id, source_route, 5),
        budget_record(route_id, 6, 1000),
        rate_record(route_id, 3, 1),
        lease_record(route_id, 2, source["actor"], units),
        pin_record(route_id, wrong_actor, source_scope, source["phase"], units, 1),
        hold_record(
            route_id, 2, source["actor"], source_scope, source["phase"], units, 1
        ),
        req_record(
            "ignored_bad_segment",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            2,
        ),
        req_record(
            "first",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        ),
        req_record(
            "lease_denial",
            route_id,
            wrong_actor,
            source_scope,
            source["phase"],
            units,
            1,
        ),
        req_record(
            "rate_denial",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        ),
        req_record(
            "after_rate_expiry",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        ),
        req_record(
            "map_last_tick",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        ),
        req_record(
            "native_after_map",
            route_id,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        ),
    ]
    assert (
        expected_decision(
            source_route,
            source["actor"],
            source_scope,
            source["phase"],
            units,
            1,
        )
        == "ALLOW"
    )
    assert run_script(binary_path, tmp_path, lines) == [
        f"first ALLOW {route_id}",
        f"lease_denial DENY {route_id}",
        f"rate_denial DENY {route_id}",
        f"after_rate_expiry ALLOW {route_id}",
        f"map_last_tick ALLOW {route_id}",
        f"native_after_map DENY {route_id}",
    ]


def test_overlay_checkpoint_rate_and_budget_share_route_clock(binary_path, tmp_path):
    """Overlay replacement, hold matching, rate, and budget age on one route clock."""
    route_id = 10
    left_route = 48
    right_route = 56
    left = route_contract(left_route)
    right = route_contract(right_route)
    units = min(left["limit"], right["limit"]) - 5
    lines = [
        map_record(route_id, 23, 2),
        pair_record(route_id, left_route, right_route, 6),
        budget_record(route_id, 5, units),
        rate_record(route_id, 3, 1),
        hold_record(
            route_id, 1, left["actor"], left["scope"], right["phase"], units, 0
        ),
        req_record(
            "hold_pair_first",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "rate_second",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "rate_third",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
        req_record(
            "budget_after_rate",
            route_id,
            left["actor"],
            left["scope"],
            right["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"hold_pair_first ALLOW {route_id}",
        f"rate_second DENY {route_id}",
        f"rate_third DENY {route_id}",
        f"budget_after_rate DENY {route_id}",
    ]


def test_invalid_lease_records_are_ignored(binary_path, tmp_path):
    """Malformed lease records should not affect later requests."""
    route_id = 10
    rule = route_contract(route_id)
    lines = [
        f"LEASE {route_id} 2 {rule['actor']}",
        lease_record(999, 1, rule["actor"], 1),
        lease_record(route_id, 0, rule["actor"], 1),
        lease_record(route_id, 1, rule["actor"], -1),
        req_record(
            "lease_clean",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            max(1, rule["limit"] // 2),
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"lease_clean ALLOW {route_id}"]


def test_seal_requires_exact_fields_until_route_ttl_expires(binary_path, tmp_path):
    """A route seal should bind fields until its own ttl expires."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 5
    lines = [
        seal_record(route_id, 2, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "seal_exact",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "seal_miss",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "seal_expired",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"seal_exact ALLOW {route_id}",
        f"seal_miss DENY {route_id}",
        f"seal_expired ALLOW {route_id}",
    ]


def test_seal_denial_does_not_spend_rate_or_budget(binary_path, tmp_path):
    """A seal denial should age ttl state without spending route capacity."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 4
    lines = [
        rate_record(route_id, 3, 1),
        budget_record(route_id, 3, units),
        seal_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "seal_budget_tick",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "seal_budget_spend",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "seal_budget_empty",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"seal_budget_tick DENY {route_id}",
        f"seal_budget_spend ALLOW {route_id}",
        f"seal_budget_empty DENY {route_id}",
    ]


def test_replayed_unsequenced_request_does_not_age_seal(binary_path, tmp_path):
    """A duplicate replay should not tick a later active route seal."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 6
    lines = [
        req_record(
            "sealReplay",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        seal_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "sealReplay",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "sealReplayFresh",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"sealReplay ALLOW {route_id}",
        f"sealReplay ALLOW {route_id}",
        f"sealReplayFresh DENY {route_id}",
    ]


def test_sequence_marker_denied_by_seal_does_not_claim_prefix(binary_path, tmp_path):
    """A seal denial before sequence binding should leave the marker reusable."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 7
    lines = [
        seal_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        req_record(
            "sealSeq:1",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "sealSeq:1",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
        req_record(
            "sealSeq:2",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"sealSeq:1 DENY {route_id}",
        f"sealSeq:1 ALLOW {route_id}",
        f"sealSeq:2 ALLOW {route_id}",
    ]


def test_invalid_seal_records_are_ignored(binary_path, tmp_path):
    """Malformed seal records should not create route-binding state."""
    route_id = 56
    rule = route_contract(route_id)
    alternate_scope = other(SCOPES, rule["scope"])
    units = rule["limit"] + 3
    lines = [
        f"SEAL {route_id} 2 {rule['actor']} {rule['scope']} {rule['phase']} {units}",
        seal_record(999, 1, rule["actor"], rule["scope"], rule["phase"], units, 1),
        seal_record(route_id, 0, rule["actor"], rule["scope"], rule["phase"], units, 1),
        seal_record(route_id, 1, rule["actor"], rule["scope"], rule["phase"], units, 2),
        req_record(
            "seal_clean",
            route_id,
            rule["actor"],
            alternate_scope,
            rule["phase"],
            units,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [f"seal_clean ALLOW {route_id}"]


@pytest.mark.parametrize("route_id", [0, 17, 48, 55, 80, 127])
def test_segment_marker_does_not_bypass_non_state_routes(
    binary_path, tmp_path, route_id
):
    """Only STATE_FLEX routes may use segment_flag to alter capacity."""
    rule = route_contract(route_id)
    req_id = f"segment_guard_{route_id:03d}"
    phase = (
        rule["phase"] if rule["mode"] != "SCOPE_FLEX" else other(STATES, rule["phase"])
    )
    line = f"REQ {req_id} {route_id} {rule['actor']} {rule['scope']} {phase} 1 1"
    assert (
        expected_decision(route_id, rule["actor"], rule["scope"], phase, 1, 1) == "DENY"
    )
    assert run_script(binary_path, tmp_path, [line]) == [f"{req_id} DENY {route_id}"]


@pytest.mark.parametrize("route_id", list(range(0, 48)))
def test_strict_routes_reject_wrong_actor(binary_path, tmp_path, route_id):
    """Strict early routes must reject requests with actor drift."""
    rule = route_contract(route_id)
    req_id = f"actor_{route_id:03d}"
    req_actor = other(ROLES, rule["actor"])
    units = max(1, rule["limit"] // 4)
    line = (
        f"REQ {req_id} {route_id} {req_actor} {rule['scope']} {rule['phase']} {units} 0"
    )
    expected = expected_decision(
        route_id, req_actor, rule["scope"], rule["phase"], units, 0
    )
    assert expected == "DENY"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(0, 16)))
def test_strict_routes_reject_oversized_units(binary_path, tmp_path, route_id):
    """Strict capacity limits must use the documented route formula."""
    rule = route_contract(route_id)
    units = rule["limit"] + 40
    req_id = f"units_{route_id:03d}"
    line = req_record(
        req_id, route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "DENY"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(0, 16)))
def test_early_strict_routes_accept_exact_matches(binary_path, tmp_path, route_id):
    """Early strict routes must allow requests that match every identity field."""
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 2)
    req_id = f"early_ok_{route_id:03d}"
    line = (
        f"REQ {req_id} {route_id} {rule['actor']} "
        f"{rule['scope']} {rule['phase']} {units} 0"
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(0, 16)))
def test_early_strict_routes_reject_scope_and_phase_drift(
    binary_path, tmp_path, route_id
):
    """Early strict routes must deny valid-capacity requests with identity drift."""
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 2)
    scope_req = f"early_scope_{route_id:03d}"
    phase_req = f"early_phase_{route_id:03d}"
    wrong_scope = other(SCOPES, rule["scope"])
    wrong_phase = other(STATES, rule["phase"])
    lines = [
        (
            f"REQ {scope_req} {route_id} {rule['actor']} "
            f"{wrong_scope} {rule['phase']} {units} 0"
        ),
        (
            f"REQ {phase_req} {route_id} {rule['actor']} "
            f"{rule['scope']} {wrong_phase} {units} 0"
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{scope_req} DENY {route_id}",
        f"{phase_req} DENY {route_id}",
    ]


@pytest.mark.parametrize("route_id", list(range(16, 48)))
def test_mid_strict_routes_accept_exact_matches(binary_path, tmp_path, route_id):
    """Middle strict routes must use the documented identity fields."""
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 2)
    req_id = f"mid_ok_{route_id:03d}"
    line = req_record(
        req_id, route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(16, 48)))
def test_mid_strict_routes_reject_oversized_units(binary_path, tmp_path, route_id):
    """Middle strict routes must enforce their capacity limits."""
    rule = route_contract(route_id)
    units = rule["limit"] + 1
    req_id = f"mid_cap_{route_id:03d}"
    line = req_record(
        req_id, route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "DENY"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(16, 48)))
def test_mid_strict_routes_reject_scope_and_phase_drift(
    binary_path, tmp_path, route_id
):
    """Middle strict routes must reject scope and phase drift."""
    rule = route_contract(route_id)
    units = max(1, rule["limit"] // 2)
    scope_req = f"mid_scope_{route_id:03d}"
    phase_req = f"mid_phase_{route_id:03d}"
    wrong_scope = other(SCOPES, rule["scope"])
    wrong_phase = other(STATES, rule["phase"])
    lines = [
        req_record(
            scope_req, route_id, rule["actor"], wrong_scope, rule["phase"], units, 0
        ),
        req_record(
            phase_req, route_id, rule["actor"], rule["scope"], wrong_phase, units, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{scope_req} DENY {route_id}",
        f"{phase_req} DENY {route_id}",
    ]


@pytest.mark.parametrize("route_id", list(range(48, 64)))
def test_live_flexible_routes_accept_documented_variance(
    binary_path, tmp_path, route_id
):
    """Routes 48 through 63 must implement their flexible production modes."""
    rule = route_contract(route_id)
    req_id = f"flex_{route_id:03d}"
    if rule["mode"] == "SCOPE_FLEX":
        req_phase = other(STATES, rule["phase"])
        req_scope = rule["scope"]
    else:
        req_phase = rule["phase"]
        req_scope = other(SCOPES, rule["scope"])
    units = max(1, rule["limit"] // 3)
    line = req_record(req_id, route_id, rule["actor"], req_scope, req_phase, units, 0)
    expected = expected_decision(
        route_id, rule["actor"], req_scope, req_phase, units, 0
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(64, 80)))
def test_upper_flexible_routes_accept_documented_variance(
    binary_path, tmp_path, route_id
):
    """Routes 64 through 79 must implement their flexible production modes."""
    rule = route_contract(route_id)
    req_id = f"upper_flex_{route_id:03d}"
    if rule["mode"] == "SCOPE_FLEX":
        req_phase = other(STATES, rule["phase"])
        req_scope = rule["scope"]
        segment = 0
        units = max(1, rule["limit"] // 3)
    else:
        req_phase = rule["phase"]
        req_scope = other(SCOPES, rule["scope"])
        segment = 1
        units = rule["limit"] + 10
    line = req_record(
        req_id, route_id, rule["actor"], req_scope, req_phase, units, segment
    )
    expected = expected_decision(
        route_id, rule["actor"], req_scope, req_phase, units, segment
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


def test_sequence_marker_suffix_boundaries_and_invalid_replay(binary_path, tmp_path):
    """Sequence suffix bounds should separate sequenced streams from replay keys."""
    route_id = 0
    rule = route_contract(route_id)
    route_one = route_contract(1)
    lines = []
    expected = []
    for seq in range(1, 4097):
        request_id = f"maxSeq:{seq}"
        lines.append(
            req_record(
                request_id,
                route_id,
                rule["actor"],
                rule["scope"],
                rule["phase"],
                1,
                0,
            )
        )
        expected.append(f"{request_id} ALLOW {route_id}")
    lines.append(
        req_record(
            "maxSeq:4097",
            route_id,
            other(ROLES, rule["actor"]),
            rule["scope"],
            rule["phase"],
            1,
            0,
        )
    )
    expected.append(f"maxSeq:4097 DENY {route_id}")
    lines.append(
        req_record(
            "maxSeq:4097",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            1,
            0,
        )
    )
    expected.append(f"maxSeq:4097 DENY {route_id}")
    for request_id in ["badSeq:0", "badSeq:-1", "badSeq:nan", ":1", "badSeq:"]:
        lines.append(
            req_record(
                request_id,
                route_id,
                rule["actor"],
                rule["scope"],
                rule["phase"],
                1,
                0,
            )
        )
        expected.append(f"{request_id} ALLOW {route_id}")
        lines.append(
            req_record(
                request_id,
                1,
                route_one["actor"],
                route_one["scope"],
                route_one["phase"],
                1,
                0,
            )
        )
        expected.append(f"{request_id} ALLOW {route_id}")
    assert run_script(binary_path, tmp_path, lines) == expected


def test_mixed_script_enforces_independent_route_contracts(binary_path, tmp_path):
    """A mixed script must keep each route's own rule and output order."""
    lines = []
    expected = []

    def add_case(req_id, route_id, actor, scope, phase, units, segment):
        lines.append(
            f"REQ {req_id} {route_id} {actor} {scope} {phase} {units} {segment}"
        )
        decision = expected_decision(route_id, actor, scope, phase, units, segment)
        expected.append(f"{req_id} {decision} {route_id}")

    for route_id in [3, 80, 127]:
        rule = route_contract(route_id)
        add_case(
            f"mix_ok_{route_id:03d}",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            max(1, rule["limit"] // 2),
            0,
        )

    strict_phase = route_contract(14)
    add_case(
        "mix_phase_014",
        14,
        strict_phase["actor"],
        strict_phase["scope"],
        other(STATES, strict_phase["phase"]),
        max(1, strict_phase["limit"] // 2),
        0,
    )

    strict_capacity = route_contract(23)
    add_case(
        "mix_cap_023",
        23,
        strict_capacity["actor"],
        strict_capacity["scope"],
        strict_capacity["phase"],
        strict_capacity["limit"] + 1,
        0,
    )

    scope_flex = route_contract(48)
    add_case(
        "mix_scope_flex_048",
        48,
        scope_flex["actor"],
        scope_flex["scope"],
        other(STATES, scope_flex["phase"]),
        max(1, scope_flex["limit"] // 2),
        0,
    )

    scope_flex_deny = route_contract(55)
    add_case(
        "mix_scope_deny_055",
        55,
        scope_flex_deny["actor"],
        other(SCOPES, scope_flex_deny["scope"]),
        scope_flex_deny["phase"],
        max(1, scope_flex_deny["limit"] // 2),
        0,
    )

    state_flex = route_contract(56)
    add_case(
        "mix_state_flex_056",
        56,
        state_flex["actor"],
        other(SCOPES, state_flex["scope"]),
        state_flex["phase"],
        state_flex["limit"] + 10,
        1,
    )

    state_flex_deny = route_contract(63)
    add_case(
        "mix_state_cap_063",
        63,
        state_flex_deny["actor"],
        state_flex_deny["scope"],
        state_flex_deny["phase"],
        state_flex_deny["limit"] + 1,
        0,
    )

    protected_scope = route_contract(64)
    add_case(
        "mix_protected_scope_064",
        64,
        protected_scope["actor"],
        protected_scope["scope"],
        other(STATES, protected_scope["phase"]),
        max(1, protected_scope["limit"] // 2),
        0,
    )

    protected_state = route_contract(72)
    add_case(
        "mix_protected_state_072",
        72,
        protected_state["actor"],
        other(SCOPES, protected_state["scope"]),
        protected_state["phase"],
        protected_state["limit"] + 10,
        1,
    )

    protected_state_deny = route_contract(79)
    add_case(
        "mix_protected_phase_079",
        79,
        protected_state_deny["actor"],
        protected_state_deny["scope"],
        other(STATES, protected_state_deny["phase"]),
        max(1, protected_state_deny["limit"] // 2),
        1,
    )

    tail_phase = route_contract(104)
    add_case(
        "mix_tail_phase_104",
        104,
        tail_phase["actor"],
        tail_phase["scope"],
        other(STATES, tail_phase["phase"]),
        max(1, tail_phase["limit"] // 2),
        0,
    )

    assert run_script(binary_path, tmp_path, lines) == expected


@pytest.mark.parametrize("route_id", list(range(80, 96)))
def test_late_strict_routes_still_accept_exact_matches(binary_path, tmp_path, route_id):
    """Late strict routes should keep their exact-match behavior."""
    rule = route_contract(route_id)
    req_id = f"strict_{route_id:03d}"
    units = max(1, rule["limit"] // 2)
    line = req_record(
        req_id, route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(80, 96)))
def test_late_strict_routes_reject_actor_scope_and_capacity_drift(
    binary_path, tmp_path, route_id
):
    """Late strict routes must deny wrong identity fields and high units."""
    rule = route_contract(route_id)
    actor_req = f"late_actor_{route_id:03d}"
    scope_req = f"late_scope_{route_id:03d}"
    units_req = f"late_units_{route_id:03d}"
    wrong_actor = other(ROLES, rule["actor"])
    wrong_scope = other(SCOPES, rule["scope"])
    valid_units = max(1, rule["limit"] // 2)
    high_units = rule["limit"] + 1
    lines = [
        req_record(
            actor_req,
            route_id,
            wrong_actor,
            rule["scope"],
            rule["phase"],
            valid_units,
            0,
        ),
        req_record(
            scope_req,
            route_id,
            rule["actor"],
            wrong_scope,
            rule["phase"],
            valid_units,
            0,
        ),
        req_record(
            units_req,
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            high_units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{actor_req} DENY {route_id}",
        f"{scope_req} DENY {route_id}",
        f"{units_req} DENY {route_id}",
    ]


@pytest.mark.parametrize("route_id", list(range(96, 128)))
def test_tail_strict_routes_accept_exact_matches(binary_path, tmp_path, route_id):
    """Tail strict routes must allow exact actor, scope, phase, and capacity."""
    rule = route_contract(route_id)
    req_id = f"tail_ok_{route_id:03d}"
    units = max(1, rule["limit"] // 2)
    line = req_record(
        req_id, route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    expected = expected_decision(
        route_id, rule["actor"], rule["scope"], rule["phase"], units, 0
    )
    assert expected == "ALLOW"
    assert run_script(binary_path, tmp_path, [line]) == [
        f"{req_id} {expected} {route_id}"
    ]


@pytest.mark.parametrize("route_id", list(range(96, 128)))
def test_tail_strict_routes_reject_actor_and_phase_drift(
    binary_path, tmp_path, route_id
):
    """Tail strict routes must also enforce actor and phase identity."""
    rule = route_contract(route_id)
    actor_req = f"tail_actor_{route_id:03d}"
    phase_req = f"tail_phase_{route_id:03d}"
    wrong_actor = other(ROLES, rule["actor"])
    wrong_phase = other(STATES, rule["phase"])
    units = max(1, rule["limit"] // 2)
    lines = [
        req_record(
            actor_req, route_id, wrong_actor, rule["scope"], rule["phase"], units, 0
        ),
        req_record(
            phase_req, route_id, rule["actor"], rule["scope"], wrong_phase, units, 0
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{actor_req} DENY {route_id}",
        f"{phase_req} DENY {route_id}",
    ]


@pytest.mark.parametrize("route_id", list(range(96, 128)))
def test_tail_strict_routes_reject_scope_and_capacity_drift(
    binary_path, tmp_path, route_id
):
    """Tail strict routes must enforce both identity fields and capacity."""
    rule = route_contract(route_id)
    scope_req = f"tail_scope_{route_id:03d}"
    units_req = f"tail_units_{route_id:03d}"
    wrong_scope = other(SCOPES, rule["scope"])
    valid_units = max(1, rule["limit"] // 2)
    high_units = rule["limit"] + 1
    lines = [
        req_record(
            scope_req,
            route_id,
            rule["actor"],
            wrong_scope,
            rule["phase"],
            valid_units,
            0,
        ),
        req_record(
            units_req,
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            high_units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{scope_req} DENY {route_id}",
        f"{units_req} DENY {route_id}",
    ]


@pytest.mark.parametrize("route_id", [0, 80])
def test_sequence_policy_denial_does_not_claim_prefix(binary_path, tmp_path, route_id):
    """A policy denial after sequence validation must not commit that marker."""
    rule = route_contract(route_id)
    wrong_actor = other(ROLES, rule["actor"])
    units = max(1, rule["limit"] // 2)
    prefix = f"policyRollback{route_id}"
    lines = [
        req_record(
            f"{prefix}:1",
            route_id,
            wrong_actor,
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            f"{prefix}:1",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            f"{prefix}:2",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"{prefix}:1 DENY {route_id}",
        f"{prefix}:1 ALLOW {route_id}",
        f"{prefix}:2 ALLOW {route_id}",
    ]


def test_sequence_rate_and_budget_denials_do_not_advance(binary_path, tmp_path):
    """Rate and budget denials should roll back an otherwise valid marker."""
    route_id = 0
    rule = route_contract(route_id)
    units = 1
    lines = [
        rate_record(route_id, 1, 0),
        req_record(
            "quotaRollback:1",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "quotaRollback:1",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "quotaRollback:2",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        budget_record(route_id, 1, 0),
        req_record(
            "quotaRollback:3",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
        req_record(
            "quotaRollback:3",
            route_id,
            rule["actor"],
            rule["scope"],
            rule["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        f"quotaRollback:1 DENY {route_id}",
        f"quotaRollback:1 ALLOW {route_id}",
        f"quotaRollback:2 ALLOW {route_id}",
        f"quotaRollback:3 DENY {route_id}",
        f"quotaRollback:3 ALLOW {route_id}",
    ]


def test_sequence_family_binding_survives_overlay_lease_and_out_of_order(
    binary_path, tmp_path
):
    """Sequenced request families should bind to original mode and sort block."""
    strict0 = route_contract(0)
    strict8 = route_contract(8)
    strict16 = route_contract(16)
    scope48 = route_contract(48)
    state56 = route_contract(56)
    other_state = route_contract(57)
    lines = [
        map_record(48, 0, 4),
        lease_record(56, 3, state56["actor"], state56["limit"] + 20),
        rate_record(16, 2, 1),
        budget_record(16, 2, strict16["limit"]),
        req_record(
            "parcelF:1",
            0,
            strict0["actor"],
            strict0["scope"],
            strict0["phase"],
            max(1, strict0["limit"] // 2),
            0,
        ),
        req_record(
            "parcelF:2",
            48,
            scope48["actor"],
            scope48["scope"],
            other(STATES, scope48["phase"]),
            max(1, scope48["limit"] // 2),
            0,
        ),
        req_record(
            "parcelF:3",
            8,
            strict8["actor"],
            strict8["scope"],
            strict8["phase"],
            max(1, strict8["limit"] // 2),
            0,
        ),
        req_record(
            "parcelF:3",
            8,
            strict8["actor"],
            strict8["scope"],
            strict8["phase"],
            max(1, strict8["limit"] // 2),
            0,
        ),
        req_record(
            "parcelF:4",
            56,
            state56["actor"],
            other(SCOPES, state56["scope"]),
            state56["phase"],
            state56["limit"] + 10,
            1,
        ),
        req_record(
            "parcelF:5",
            16,
            strict16["actor"],
            strict16["scope"],
            strict16["phase"],
            strict16["limit"],
            0,
        ),
        req_record(
            "parcelF:6",
            16,
            strict16["actor"],
            strict16["scope"],
            strict16["phase"],
            1,
            0,
        ),
        req_record(
            "parcelF:1",
            57,
            other_state["actor"],
            other(SCOPES, other_state["scope"]),
            other_state["phase"],
            other_state["limit"] + 5,
            1,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        "parcelF:1 ALLOW 0",
        "parcelF:2 DENY 48",
        "parcelF:3 ALLOW 8",
        "parcelF:3 DENY 8",
        "parcelF:4 DENY 56",
        "parcelF:5 DENY 16",
        "parcelF:6 DENY 16",
        "parcelF:1 DENY 57",
    ]


def test_sequence_sort_block_drift_does_not_spend_route_quotas(binary_path, tmp_path):
    """Sort-block drift should age route controls without consuming quotas."""
    first = route_contract(0)
    drift = route_contract(16)
    units = max(1, drift["limit"] // 3)
    lines = [
        rate_record(16, 4, 1),
        budget_record(16, 4, units),
        req_record(
            "sortBlock:1",
            0,
            first["actor"],
            first["scope"],
            first["phase"],
            max(1, first["limit"] // 2),
            0,
        ),
        req_record(
            "sortBlock:2",
            16,
            drift["actor"],
            drift["scope"],
            drift["phase"],
            units,
            0,
        ),
        req_record(
            "sortBlock:3",
            16,
            drift["actor"],
            drift["scope"],
            drift["phase"],
            units,
            0,
        ),
        req_record(
            "route16:1",
            16,
            drift["actor"],
            drift["scope"],
            drift["phase"],
            units,
            0,
        ),
        req_record(
            "route16:2",
            16,
            drift["actor"],
            drift["scope"],
            drift["phase"],
            units,
            0,
        ),
        req_record(
            "route16:2",
            16,
            drift["actor"],
            drift["scope"],
            drift["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        "sortBlock:1 ALLOW 0",
        "sortBlock:2 DENY 16",
        "sortBlock:3 DENY 16",
        "route16:1 ALLOW 16",
        "route16:2 DENY 16",
        "route16:2 ALLOW 16",
    ]


def test_sequence_prefix_owner_blocks_cross_actor_hijack_without_spending(
    binary_path, tmp_path
):
    """A claimed prefix cannot be reused by another actor or spend its quotas."""
    owner = route_contract(0)
    other_actor = route_contract(1)
    units = max(1, other_actor["limit"] // 3)
    lines = [
        rate_record(1, 3, 1),
        budget_record(1, 3, units),
        req_record(
            "dock:1",
            0,
            owner["actor"],
            owner["scope"],
            owner["phase"],
            max(1, owner["limit"] // 2),
            0,
        ),
        req_record(
            "dock:1",
            1,
            other_actor["actor"],
            other_actor["scope"],
            other_actor["phase"],
            units,
            0,
        ),
        req_record(
            "financeDock:1",
            1,
            other_actor["actor"],
            other_actor["scope"],
            other_actor["phase"],
            units,
            0,
        ),
        req_record(
            "financeDock:2",
            1,
            other_actor["actor"],
            other_actor["scope"],
            other_actor["phase"],
            units,
            0,
        ),
        req_record(
            "financeDock:2",
            1,
            other_actor["actor"],
            other_actor["scope"],
            other_actor["phase"],
            units,
            0,
        ),
    ]
    assert run_script(binary_path, tmp_path, lines) == [
        "dock:1 ALLOW 0",
        "dock:1 DENY 1",
        "financeDock:1 ALLOW 1",
        "financeDock:2 DENY 1",
        "financeDock:2 ALLOW 1",
    ]
