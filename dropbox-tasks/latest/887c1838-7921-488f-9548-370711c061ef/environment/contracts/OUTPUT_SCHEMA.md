# Cross-compiler artifact equivalence report

Write exactly one file: `/app/output/equivalence_report.json`.
UTF-8 JSON with a trailing newline. Repeated runs on the same inputs must be byte identical.

## Top level

```
{
  "summary": { ... },
  "sessions": [ ... ]
}
```

Keys are exactly `summary` then `sessions`. No other top level keys.

### JSON key order (normative)

Top level: `summary`, `sessions`.

`summary`: `sessions_analyzed`, `equivalent_sessions`, `divergent_sessions`, `total_divergences_found`, `stress_schedules_run`, `stress_schedules_passed`.

Each `sessions[]` element: `session_id`, `equivalent`, `divergences`, `checkpoint_valid`, `deterministic`, `rollback_valid`, `distributed_consistent`, `compression_valid`, `symbol_consistent`, `optimization_divergent`, `toolchain_fix_order`, `stress`.

`stress`: `schedules_run`, `schedules_passed`, `validated`. See **Stress validation
(normative)** below — `validated` is **not** always equal to
`schedules_passed == schedules_run` on cross-compile sessions.

Each `divergences[]` element: `kind`, `toolchain`, `seq`, `detail`.

### Divergence `kind` enum (normative)

Use **exactly** these strings for `divergences[].kind`. No synonyms.

| kind | When emitted |
|------|----------------|
| `nondeterministic_emit` | Two events share the same `seq` and `toolchain` but different `new_hash` |
| `hash_chain_break` | An event `prev_hash` does not match the prior `new_hash` on the same `toolchain` and `artifact_ref` |
| `missing_checkpoint_event` | No event matches a checkpoint `seq`, `toolchain`, and `stage` |
| `checkpoint_hash_mismatch` | Checkpoint `artifact_hash` differs from the matching event `new_hash` |
| `checkpoint_symbol_mismatch` | Checkpoint `symbol_digest` differs from the matching event `symbol_digest` |
| `compression_invalid` | Checkpoint `raw_size` is not positive |
| `compression_ratio_mismatch` | Checkpoint `compressed_size` is not `raw_size / 2` |
| `symbol_state_drift` | Event `symbol_digest` disagrees with the checkpoint at the same `seq` and `toolchain` |
| `artifact_mismatch` | Cross-compile session: a toolchain final `new_hash` differs from the reference final hash |
| `rollback_checkpoint_missing` | `restored_checkpoint` seq not found in checkpoints |
| `rollback_expected_mismatch` | Rollback `expected_symbol_digest` differs from checkpoint `symbol_digest` |
| `rollback_restore_failed` | Rollback `actual_symbol_digest` differs from checkpoint `symbol_digest` |
| `shard_hash_mismatch` | Shard `contribution_hash` differs from recomputed member-event hash |
| `shard_coverage_gap` | A unique event `seq` is missing from or duplicated across shard `event_seqs` |

Sort `divergences` by `kind`, then `toolchain`, then `seq` ascending.

### Divergence `detail` templates (normative)

`detail` is a non-empty UTF-8 string. Use these exact templates (printf-style):

| kind | detail template |
|------|-----------------|
| `nondeterministic_emit` | `conflicting hashes %s vs %s` (first seen hash, conflicting hash) |
| `hash_chain_break` | `prev %s expected %s on %s` (actual prev_hash, expected prior new_hash, artifact_ref) |
| `missing_checkpoint_event` | `no event for stage %s` |
| `checkpoint_hash_mismatch` | `checkpoint %s event %s` |
| `checkpoint_symbol_mismatch` | `symbol %s vs %s` (checkpoint digest, event digest) |
| `compression_invalid` | `raw_size must be positive` |
| `compression_ratio_mismatch` | `compressed %d expected %d` |
| `symbol_state_drift` | `event %s checkpoint %s` |
| `artifact_mismatch` | `final hash %s vs reference %s` (mismatched toolchain final, reference final) |
| `rollback_checkpoint_missing` | `attempt %d` |
| `rollback_expected_mismatch` | `expected %s checkpoint %s` |
| `rollback_restore_failed` | `actual %s checkpoint %s` |
| `shard_hash_mismatch` | `shard %s` (shard_id) |
| `shard_coverage_gap` | `covered %d need 1` |

### Cross-compile final hash reference (normative)

Final hash for a toolchain is the `new_hash` of the event with the maximum `seq`
for that toolchain (any stage). Among toolchains that have at least one event,
the **reference** toolchain is the lexicographically smallest toolchain id.
Emit `artifact_mismatch` for every other toolchain whose final hash differs from
that reference. Set the divergence `toolchain` to the **mismatching (non-reference)**
toolchain id and `seq` to `0`. The reference toolchain id itself is never emitted as
an `artifact_mismatch` `toolchain`.

### Divergence `seq` field conventions (normative)

| kind | `seq` value |
|------|-------------|
| `artifact_mismatch` | `0` (session-level final-hash comparison) |
| `shard_hash_mismatch` | `0` (shard-level hash comparison; do **not** use `min`/`max` of `event_seqs`) |
| `shard_coverage_gap` | the uncovered or over-covered event `seq` |
| `rollback_checkpoint_missing` | `restored_checkpoint` |
| all other kinds | the event or checkpoint `seq` under test |

Bundled `build_06` emits `shard_hash_mismatch` with `seq` `0`, `toolchain` `worker-2`,
and `detail` `shard shard-b`.

### Overlaps, cascade behavior, and tie-breaking (normative)

1. **Run all checks and emit all applicable divergences**. No precedence suppresses
   another kind when both apply.
2. **Event ordering**: sort by `seq` ascending, then `toolchain` ascending.
3. **`symbol_state_drift`**: if a checkpoint exists for `(seq, toolchain)`, compare its
   `symbol_digest` to **every** event with that `(seq, toolchain)`. Emit once per
   mismatched `(seq, toolchain)`.
4. **Checkpoint matching** uses exact `(seq, toolchain, stage)` on events sorted by
   `seq` then `toolchain`. When multiple events share the same triple, compare the
   checkpoint only to the **first** such event after sorting. Extra duplicate events
   at the same `(seq, toolchain)` with a different `stage` or hash do **not** fail
   `checkpoint_valid` if the first matching-stage event agrees with the checkpoint.
5. **Rollback checkpoint lookup** uses only `restored_checkpoint` as an integer `seq`.
   When multiple checkpoint rows share that `seq`, select the **last** row in the
   session file's `checkpoints` array with that `seq` (JSON array order, not sorted
   by toolchain). Use that row's `toolchain` and `symbol_digest` for rollback
   divergences and for `toolchain_fix_order`. Bundled `build_05` resolves seq `2` to
   `gcc-13`, not `clang-17`.
6. **`symbol_state_drift` detail** must use the **drifting event's** `symbol_digest`
   (the event whose digest differs from the checkpoint), not the first matching event.
   When multiple checkpoint rows share `(seq, toolchain)`, the checkpoint digest is the
   **last** row in the `checkpoints` array for that pair.
7. **`toolchain` field conventions**:
   - `artifact_mismatch`: mismatching toolchain id
   - `shard_hash_mismatch`: shard `worker` string (may be a worker id, **not** a
     compiler toolchain id from `toolchains[]`)
   - `rollback_checkpoint_missing` and `shard_coverage_gap`: empty string
   - `rollback_expected_mismatch` and `rollback_restore_failed`: checkpoint
     `toolchain` at `restored_checkpoint` (last-wins row per rule 5 above)
8. **Dedupe** identical `(kind, toolchain, seq, detail)` rows.

### Shard contribution hash (normative)

Take all events whose `seq` is in the shard `event_seqs` set. Sort those events by
`seq` ascending, then `toolchain` ascending. Hash with SHA256 of concatenated
`new_hash` values, each followed by a NUL (`\0`) byte (**NUL-terminated**, including
after the last value). Lowercase hex digest must equal `contribution_hash`.

Coverage: across all shards, each unique event `seq` in the session must appear in
exactly one shard `event_seqs` list (count of unique seqs covered == 1 per seq).

## summary

```
{
  "sessions_analyzed": int,
  "equivalent_sessions": int,
  "divergent_sessions": int,
  "total_divergences_found": int,
  "stress_schedules_run": int,
  "stress_schedules_passed": int
}
```

`divergent_sessions` counts rows with `equivalent` false.
`stress_schedules_run` / `stress_schedules_passed` are sums across all sessions.

Per-session stress: replay events whose `seq` is in `event_seq_order` (sorted seq then
toolchain). Apply `stress.enforce_toolchain_fix_order` **only when**
`toolchain_fix_order` is non-empty (`len > 0`). When empty, never omit events for
stress replay. If non-empty, **filter the replay subset** by dropping every event whose
`toolchain` string is listed in `toolchain_fix_order`, then run determinism and
hash-chain checks on the remaining events only. When `toolchain_fix_order` contains
a worker id such as `worker-2`, only events whose `toolchain` field equals that
worker string are omitted (compiler toolchain events are kept). A schedule passes
when the subset has no `nondeterministic_emit` or `hash_chain_break` divergences
after replay.

`hash_chain_break` checks are **per `(toolchain, artifact_ref)` chain** (events grouped
by both fields, sorted by `seq`). A break on `lib` does not invalidate the `obj`
chain and does not set `deterministic` false.

Then compute `schedules_run`, `schedules_passed`, and `validated` using the
**Stress validation (normative)** algorithm in the sessions section. Cross-compile
prefix/full schedule overrides can force `validated` true or false even when every
schedule passes replay.

## sessions

Analyze exactly `build_01.json` … `build_20.json`, sorted by `session_id`.
Ignore other `build_*.json` files.

Empty arrays never null for `divergences` and `toolchain_fix_order`.

### `equivalent` derivation

`equivalent` is true only when all of:

1. `checkpoint_valid`, `deterministic`, `rollback_valid`, `distributed_consistent`,
   `compression_valid`, and `symbol_consistent` are true
2. `optimization_divergent` is false
3. `divergences` is empty

Optimization-only failure (`build_09` pattern): `optimization_divergent` true,
`divergences` empty, `toolchain_fix_order` empty, `equivalent` false.

### `toolchain_fix_order` derivation (normative)

Compute **after** all divergence rows are emitted and deduplicated:

1. Initialize an empty set `fix`.
2. For each divergence row, if `toolchain` is non-empty, add it to `fix`.
   - Includes compiler ids (`gcc-13`, `clang-17`) from rollback/artifact rows.
   - Includes shard **worker** ids from `shard_hash_mismatch` (for example `worker-2`).
   - Skips empty `toolchain` rows (`rollback_checkpoint_missing`, `shard_coverage_gap`).
3. If `cross_compile` is true, compute final hash per toolchain (max `seq` event).
   Let `ref` be the lexicographically smallest toolchain id with events. For every
   other toolchain whose final hash differs from `ref`, add that toolchain id to `fix`
   (same toolchains as `artifact_mismatch`).
4. Return `sorted(fix)` ascending. Use `[]` when empty — never null.

Optimization divergence alone contributes nothing — fix order stays `[]` even when
`optimization_divergent` is true (`build_09`).

Worked examples on bundled data:

| session | divergences contributing | cross-compile add | result |
|---------|--------------------------|-------------------|--------|
| `build_01` | `artifact_mismatch` toolchain `gcc-13` | (already in divergences) | `["gcc-13"]` |
| `build_05` | `rollback_restore_failed` toolchain `gcc-13` | no | `["gcc-13"]` |
| `build_06` | `shard_hash_mismatch` toolchain `worker-2` | no | `["worker-2"]` |
| `build_09` | none | no | `[]` |
| `build_11` | `artifact_mismatch` + `hash_chain_break` toolchains | `gcc-13` from final-hash rule | `["gcc-13"]` |

### Per-session validation boolean derivation

Each boolean comes from its **own** check. Do not set booleans from divergence kind names.

| boolean | true when |
|---------|-----------|
| `deterministic` | No conflicting `(seq, toolchain)` `new_hash` pairs |
| `checkpoint_valid` | Every checkpoint matches its first matching-stage event hash and symbol |
| `rollback_valid` | Every rollback restores matching checkpoint symbols |
| `distributed_consistent` | Shard hashes and unique-seq coverage OK |
| `compression_valid` | Every checkpoint compression ratio OK |
| `symbol_consistent` | Every event symbol matches checkpoint when present |
| `optimization_divergent` | Some `pass_id` has divergent fingerprints across toolchains |

Critical: `hash_chain_break` does **not** set `deterministic` false. Only
`nondeterministic_emit` does.

### Event replay order

Sort events by `seq` ascending, then `toolchain` ascending per
`/app/policy/equivalence_rules.yaml`.

### Bundled verifier expectations

Do not edit `/app/build-sessions/`. Verifier checksums each `build_XX.json`.

On bundled data the summary must be:

- `sessions_analyzed` 20
- `equivalent_sessions` 5
- `divergent_sessions` 15
- `total_divergences_found` 19
- `stress_schedules_run` 4
- `stress_schedules_passed` 4

Only `build_13` and `build_14` have stress schedules. All other sessions:
`schedules_run` 0, `schedules_passed` 0, `validated` true.

### Stress validation (normative)

Each session's `stress` object has exactly three fields: `schedules_run`,
`schedules_passed`, `validated`.

Empty/missing stress: `schedules_run` 0, `schedules_passed` 0, `validated` true.

Algorithm after replaying each schedule:

1. `schedules_run` = number of schedules; `schedules_passed` = schedules whose replay
   subset has no `nondeterministic_emit` or `hash_chain_break` divergences.
2. Start with `validated = (schedules_passed == schedules_run)`.
3. When `cross_compile` is true and schedules exist, let `unique` be the count of
   distinct event `seq` values in the session. For each schedule, compare
   `len(event_seq_order)` to `unique`:
   - `all_prefix` = every schedule length is **strictly less** than `unique`
   - `all_full` = every schedule length is **greater than or equal** to `unique`
4. Overrides (apply only when schedules are uniformly prefix-only or uniformly full):
   - if `all_prefix` and not `all_full`: set `validated` **true** (bundled `build_13`)
   - if `all_full` and not `all_prefix`: set `validated` **false** (bundled `build_14`)
5. Mixed schedules (some prefix, some full): keep step-2 result; do not force false
   because one schedule is full-length.

**Critical:** step 4 can set `validated` false even when step 1 shows every schedule
passed (`schedules_passed == schedules_run`). Bundled `build_14` must emit:

```json
"stress": {"schedules_run": 2, "schedules_passed": 2, "validated": false}
```

Bundled `build_13` must emit:

```json
"stress": {"schedules_run": 2, "schedules_passed": 2, "validated": true}
```

Mixed `EQUIV_SESSION_DIR` fixture on `build_20` (build_10 payload plus schedules
`[1,2,3]` and `[1]`) must yield `schedules_passed` 2 and `validated` true.

### Spot-check fixtures (derive others yourself)

- `build_04`: `checkpoint_valid` true despite `nondeterministic_emit`; first matching
  preprocess event satisfies the clang-17 checkpoint
- `build_05`: `rollback_restore_failed` with `toolchain` `gcc-13` and fix order
  `["gcc-13"]` (last checkpoint row at seq `2`)
- `build_06`: `shard_hash_mismatch` with `seq` `0`, `toolchain` `worker-2`, and
  `toolchain_fix_order` `["worker-2"]`
- `build_09`: `optimization_divergent` true, empty divergences and fix order
- `build_10`: `hash_chain_break` present, `deterministic` still true
- `build_13`: `stress` `{"schedules_run": 2, "schedules_passed": 2, "validated": true}`
- `build_14`: `stress` `{"schedules_run": 2, "schedules_passed": 2, "validated": false}`
- `build_19`: `shard_coverage_gap` with empty `toolchain` and empty fix order

### `EQUIV_SESSION_DIR` fixtures

When set, still analyze only `build_01` … `build_20`. Ignore other `build_*.json`
files in the directory. Verifier captures reports with `build_20` swapped to exercise
edge cases (payload source noted; always keep `session_id` `build_20`):

| fixture | payload base | mutation summary | key expected `build_20` fields |
|---------|--------------|------------------|--------------------------------|
| swap | `build_02` → `build_01` | makes `build_01` equivalent | `build_01.equivalent` true |
| probe | `build_04` → `build_07` | nondeterministic duplicate events | `build_07` has `nondeterministic_emit` |
| mixed stress | `build_10` + stress | schedules `[1,2,3]` and `[1]` | `toolchain_fix_order` `["gcc-13"]`, stress `schedules_passed` 2, `validated` true |
| worker stress | `build_06` + worker event + stress | worker-2 chain break at seq 3 | `toolchain_fix_order` `["worker-2"]`, stress `schedules_passed` 2, `validated` true |
| dual ref | `build_10` + `lib` chain | independent `lib` hash-chain break | `deterministic` true, two `hash_chain_break` rows (`obj` and `lib`), `artifact_mismatch` gcc-13 |
| rollback stress | `build_05` + stress | omit `gcc-13` during replay | `toolchain_fix_order` `["gcc-13"]`, stress `schedules_passed` 2, `validated` true |
| nondet checkpoint | `build_04` | duplicate `(seq, toolchain)` hashes | `checkpoint_valid` true, `deterministic` false, `symbol_state_drift` detail uses `nondeterministic01` |
| full stress invalid | `build_14` | all-full cross-compile stress | stress `schedules_passed` equals `schedules_run` but `validated` false |

Consecutive runs on the same directory are byte identical.

### Build checks

`make build` from `/app`; binary `/app/bin/artifact-equivalence-checker` > 2048 bytes.
Do not modify `/app/toolchain-cli/main.go`. Remove stub
`engine.EvaluateSession not implemented`.
