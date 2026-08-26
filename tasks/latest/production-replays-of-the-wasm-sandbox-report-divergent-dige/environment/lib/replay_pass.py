"""Replay execution pass from a saved checkpoint."""
# ruff: noqa: F841, F401

from __future__ import annotations

from lib.access import cap_remaining, check_cap, restore_uses, spend_cap
from lib.audit import apply_baseline_merge, cap_drift_score, record_escalation
from lib.boundary import is_escape_attempt
from lib.budget import charge_fuel, init_fuel
from lib.journal import spent_uses


def run_replay_pass(runtime, checkpoint: dict, generation: int) -> None:
    runtime._generation = generation
    runtime.executed = 0
    runtime.fuel_used = 0
    runtime.violations = 0
    runtime.escapes = 0
    runtime.cap_drift = 0
    runtime.fuel = init_fuel(runtime.fuel_budget)
    runtime.fuel["remaining"] = int(checkpoint.get("fuel_remaining", runtime.fuel_budget))
    snap_caps = checkpoint.get("caps", {})
    for cid, snap in snap_caps.items():
        cap = runtime.caps.get(cid, {})
        apply_baseline_merge(cap, list(snap.get("ops", [])))
        restore_uses(
            cap,
            int(snap.get("uses_left", 0)),
            spent_uses(int(snap.get("uses_left", 0)), cap_remaining(cap)),
        )
    for call in list(checkpoint.get("host_calls", [])):
        cap_id = call.get("cap")
        op = call.get("op", "read")
        cap = runtime.caps.get(cap_id, {})
        if record_escalation(cap, op):
            runtime.cap_drift += 1
        if not check_cap(cap, op):
            runtime.violations += 1
            continue
        if is_escape_attempt(call):
            runtime.escapes += 1
            runtime.violations += 1
            continue
        spend = call.get("fuel", 5)
        if not charge_fuel(runtime.fuel, spend):
            runtime.violations += 1
            continue
        runtime.fuel_used += spend
        spend_cap(runtime.caps[cap_id], op)
        runtime.executed += 1
    runtime.cap_drift += cap_drift_score(runtime.caps)
