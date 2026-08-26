"""WASM runtime with fuel limits and capability-gated host calls."""
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
