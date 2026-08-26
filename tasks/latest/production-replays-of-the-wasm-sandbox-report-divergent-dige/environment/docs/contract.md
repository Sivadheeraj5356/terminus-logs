# Contract

## Metrics

`WasmRuntime.run()` and `WasmRuntime.run_replay()` return a five-int tuple in this order:

1. `executed` — module steps and successful host calls that completed after fuel and capability checks
2. `fuel_used` — total fuel charged across completed module steps and host calls
3. `violations` — refused module steps (insufficient fuel), refused host calls (capability or fuel), and other policy failures counted by the runtime
4. `escapes` — host calls classified as sandbox escape attempts
5. `cap_drift` — per-call escalation events plus the aggregate drift score computed from capability state at the end of the run

Do not return a dict or add keys. Preserve the tuple return type.

## Digest

`digest = SHA256(repr(metrics))[:16]` where `metrics` is the tuple above.

## Fuel

`init_fuel(budget)` sets `remaining` to the non-negative budget. `charge_fuel(state, cost)` succeeds without changing `remaining` when `cost <= 0`. Otherwise it fails when `remaining < cost`; on success it subtracts `cost` from `remaining` and returns true. Module execution that cannot charge fuel increments `violations` and skips the step.

## Capabilities

Each capability has `ops` (allowed operation names), optional `baseline_ops` (defaults to a copy of `ops` at runtime init if omitted), and `uses_left` (remaining host-call budget for that token).

`check_cap(cap, op)` requires a non-empty cap, `op` in `ops`, and `uses_left > 0`. `spend_cap(cap, op)` decrements `uses_left` by one (floored at zero) when `op` is in `ops`. A host call that fails capability or fuel checks increments `violations` and is not executed.

## Escape detection

`is_escape_attempt(call)` is true when `call["escape"]` is truthy or when `call["op"]` is one of `host`, `memory`, `proc`, `env`, or `fs_root`. Escape attempts increment both `escapes` and `violations`; they are not executed and do not spend fuel or capability uses. Escape classification runs before capability checks on every host-call pass.

## Capability drift

`record_escalation(cap, op)` is true when the call's `op` is currently allowed but not in that cap's `baseline_ops`. Each true result increments runtime `cap_drift` before the host call is attempted.

`cap_drift_score(caps)` sums, over every capability, the count of operations in `ops` that are not in `baseline_ops`. The runtime adds this total to `cap_drift` after all modules and host calls finish.

## Checkpoint and replay

After a live run, the runtime writes `/app/data/wasm/checkpoint.json` with `fuel_remaining` (remaining fuel after the live pass), per-capability snapshots (`ops`, `baseline_ops`, `uses_left`), and the host-call journal.

`run_replay(checkpoint, generation)` restores capability state from the snapshot, merges `ops` with the saved snapshot via `apply_baseline_merge`, and restores `uses_left` by subtracting live spends from the snapshot count. Replay executes only the saved host calls under the bumped generation.

## Observation export

`/app/environment/ops/probe/run-audit.sh` replays `/app/environment/fixtures/waves/recovery-wave.json` and writes `/app/output/sandbox_observations.json`:

```json
{
  "runs": [
    {"label": "live", "generation": 0, "sandbox_digest": "...", "metrics": [..], "segments": [{"source": "budget|access|boundary|audit", ...}]},
    {"label": "replay", "generation": 1, "sandbox_digest": "...", "metrics": [..], "segments": [{"source": "journal", ...}]}
  ],
  "probes": {
    "live_digest": "...",
    "replay_digest": "...",
    "ledger_gap": "<abs live fuel_used - replay fuel_used>",
    "stale_token_count": "<count>",
    "escalation_delta": "<replay cap_drift - live cap_drift>"
  }
}
```

`ledger_gap` is the absolute difference between live and replay `fuel_used`. `stale_token_count` counts capabilities whose snapshot still shows remaining uses while replay executed fewer host calls than the live pass. `escalation_delta` is replay `cap_drift` minus live `cap_drift`.

## Journal fields

Scenario JSON uses `modules` (or `ops`), optional `host_calls`, `fuel_budget`, optional `profile_generation`, and `capabilities`. Module objects carry optional `fuel` (default 10). Host-call objects carry `cap`, optional `op` (default `read`), optional `fuel` (default 5), and optional `escape`.

Some scenarios include `alt_ops` — a second module list replayed with the same host calls, fuel budget, and capabilities. Reordering modules must change `digest`; the verifier compares the primary replay to `expected_digest` and the alternate replay to `alt_expected_digest`.

Coupled recovery scenarios use `/app/data/wasm/recovery-coupling` for isolated checkpoint storage during grading. The hidden coupled scenario is named `replay_coupling_trap` under `/tests/fixtures/wasm/`.

Recovery scenarios may include `expected_live_digest`, `expected_replay_digest`, and `expected_probes` for coupled live/replay witnesses. The recovery wave bundles converged witness values in `/app/environment/fixtures/waves/recovery-witness.json`.

Source under `/app/environment` must satisfy this contract.
