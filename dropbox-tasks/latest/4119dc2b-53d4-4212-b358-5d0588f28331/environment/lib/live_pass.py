"""Live execution pass for module and host-call phases."""
# ruff: noqa: F841, F401

from __future__ import annotations

from lib.access import check_cap, spend_cap
from lib.audit import cap_drift_score, record_escalation
from lib.boundary import is_escape_attempt
from lib.budget import charge_fuel


def run_live(runtime) -> None:
    for mod in runtime.modules:
        cost = mod.get("fuel", 10)
        if not charge_fuel(runtime.fuel, cost):
            continue
        runtime.fuel_used += cost
        runtime.executed += 1
    for call in runtime.host_calls:
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
