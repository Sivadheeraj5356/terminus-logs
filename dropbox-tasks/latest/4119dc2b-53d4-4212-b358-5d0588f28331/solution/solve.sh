#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

root = Path("/app/environment")

(root / "lib/budget.py").write_text(
    '''"""Fuel budget tracking for WASM execution."""
# ruff: noqa: F841, F401

from __future__ import annotations


def init_fuel(budget: int) -> dict[str, int]:
    return {"remaining": max(0, budget)}


def charge_fuel(state: dict[str, int], cost: int) -> bool:
    if cost <= 0:
        return True
    if state["remaining"] < cost:
        return False
    state["remaining"] -= cost
    return True


def refund_fuel(state: dict[str, int], amount: int) -> bool:
    if amount <= 0:
        return True
    state["remaining"] += amount
    return True


def ledger_total(state: dict[str, int], spent: int) -> int:
    return int(state.get("remaining", 0)) + int(spent)
'''
)

(root / "lib/access.py").write_text(
    '''"""Capability token validation and spend tracking."""
# ruff: noqa: F841, F401

from __future__ import annotations


def check_cap(cap: dict, op: str) -> bool:
    if not cap:
        return False
    allowed = cap.get("ops", [])
    uses = cap.get("uses_left", 0)
    return op in allowed and uses > 0


def spend_cap(cap: dict, op: str) -> None:
    if op in cap.get("ops", []):
        cap["uses_left"] = max(0, int(cap.get("uses_left", 0)) - 1)


def restore_uses(cap: dict, snapshot_uses: int, live_spent: int) -> None:
    cap["uses_left"] = max(0, int(snapshot_uses) - int(live_spent))


def renew_cap(cap: dict, uses: int) -> None:
    if uses > 0:
        cap["uses_left"] = uses


def cap_remaining(cap: dict) -> int:
    return int(cap.get("uses_left", 0))
'''
)

(root / "lib/boundary.py").write_text(
    '''"""Sandbox escape attempt detection."""
# ruff: noqa: F841, F401

from __future__ import annotations

_FORBIDDEN = frozenset({"host", "memory", "proc", "env", "fs_root"})


def is_escape_attempt(call: dict) -> bool:
    if call.get("escape"):
        return True
    op = call.get("op", "read")
    return op in _FORBIDDEN


def abuse_score(calls: list[dict]) -> int:
    return sum(1 for c in calls if is_escape_attempt(c))


def probe_escape(op: str) -> bool:
    return op not in _FORBIDDEN
'''
)

(root / "lib/audit.py").write_text(
    '''"""Capability drift and escalation tracking."""
# ruff: noqa: F841, F401

from __future__ import annotations


def record_escalation(cap: dict, op: str) -> bool:
    if not cap:
        return False
    baseline = set(cap.get("baseline_ops", cap.get("ops", [])))
    allowed = set(cap.get("ops", []))
    return op in allowed and op not in baseline


def cap_drift_score(caps: dict[str, dict]) -> int:
    total = 0
    for cap in caps.values():
        baseline = set(cap.get("baseline_ops", []))
        current = set(cap.get("ops", []))
        total += len(current - baseline)
    return total


def drift_delta(cap: dict) -> int:
    baseline = set(cap.get("baseline_ops", []))
    current = set(cap.get("ops", []))
    return len(baseline - current)


def apply_baseline_merge(cap: dict, snapshot_ops: list[str]) -> None:
    cap["ops"] = list(set(cap.get("ops", [])) | set(snapshot_ops))
'''
)

journal = root / "lib/journal.py"
journal.write_text(
    journal.read_text().replace(
        '"fuel_remaining": fuel.get("remaining", 0) + fuel_used,',
        '"fuel_remaining": fuel.get("remaining", 0),',
    )
)

(root / "lib/live_pass.py").write_text(
    '''"""Live execution pass for module and host-call phases."""
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
            runtime.violations += 1
            continue
        runtime.fuel_used += cost
        runtime.executed += 1
    for call in runtime.host_calls:
        if is_escape_attempt(call):
            runtime.escapes += 1
            runtime.violations += 1
            continue
        cap_id = call.get("cap")
        op = call.get("op", "read")
        cap = runtime.caps.get(cap_id, {})
        if record_escalation(cap, op):
            runtime.cap_drift += 1
        if not check_cap(cap, op):
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
'''
)

(root / "lib/replay_pass.py").write_text(
    '''"""Replay execution pass from a saved checkpoint."""
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
        if is_escape_attempt(call):
            runtime.escapes += 1
            runtime.violations += 1
            continue
        cap_id = call.get("cap")
        op = call.get("op", "read")
        cap = runtime.caps.get(cap_id, {})
        if record_escalation(cap, op):
            runtime.cap_drift += 1
        if not check_cap(cap, op):
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
'''
)

(root / "structlib/wasm_runtime.py").write_text(
    '''"""WASM runtime with fuel limits and capability-gated host calls."""
# ruff: noqa: F841, F401

from __future__ import annotations

from lib.budget import init_fuel
from lib.live_pass import run_live
from lib.replay_pass import run_replay_pass


class WasmRuntime:
    def __init__(self, spec: dict) -> None:
        self.modules = list(spec.get("ops", spec.get("modules", [])))
        self.host_calls = list(spec.get("host_calls", []))
        self.fuel_budget = spec.get("fuel_budget", 100)
        self.caps = {c["id"]: dict(c) for c in spec.get("capabilities", [])}
        for cap in self.caps.values():
            cap.setdefault("baseline_ops", list(cap.get("ops", [])))
        self.fuel = init_fuel(self.fuel_budget)
        self.executed = 0
        self.fuel_used = 0
        self.violations = 0
        self.escapes = 0
        self.cap_drift = 0
        self._generation = int(spec.get("profile_generation", 0))

    def run(self) -> tuple[int, int, int, int, int]:
        run_live(self)
        return self.executed, self.fuel_used, self.violations, self.escapes, self.cap_drift

    def run_replay(self, checkpoint: dict, generation: int) -> tuple[int, int, int, int, int]:
        run_replay_pass(self, checkpoint, generation)
        return self.executed, self.fuel_used, self.violations, self.escapes, self.cap_drift

    @staticmethod
    def metrics_digest(metrics: tuple[int, int, int, int, int]) -> str:
        import hashlib

        return hashlib.sha256(repr(metrics).encode()).hexdigest()[:16]

    @staticmethod
    def probe_map(live: tuple[int, int, int, int, int], replay: tuple[int, int, int, int, int], checkpoint: dict) -> dict[str, str]:
        snap_caps = checkpoint.get("caps", {})
        stale = 0
        for snap in snap_caps.values():
            if int(snap.get("uses_left", 0)) > 0 and replay[0] < live[0]:
                stale += 1
        return {
            "live_digest": WasmRuntime.metrics_digest(live),
            "replay_digest": WasmRuntime.metrics_digest(replay),
            "ledger_gap": str(abs(live[1] - replay[1])),
            "stale_token_count": str(stale),
            "escalation_delta": str(replay[4] - live[4]),
        }
'''
)
PY

grep -q 'run_live' /app/environment/lib/live_pass.py
grep -q 'run_replay_pass' /app/environment/lib/replay_pass.py
grep -q 'uses > 0' /app/environment/lib/access.py
grep -q 'current - baseline' /app/environment/lib/audit.py
