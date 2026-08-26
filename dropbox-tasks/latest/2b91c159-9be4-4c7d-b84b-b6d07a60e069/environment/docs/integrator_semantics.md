# Integrator semantics

Normative behavioral spec for the checkpointed `demo_engine` recovery reports. The platform verifier compares emitted JSON against an independent expected model; agents cannot read private harness sources under `/tests/` during execution. Repair C++ under `/app/environment` so rebuilt binaries match these semantics exactly.

Build and emit: `docs/runtime_contract.txt`, `README.build`, `scripts/emit_matrix.sh`, `demo_engine trace <QTOKEN>`, and journal replay commands documented in `instruction.md`.

## Report fields

Each scene token `Q0`–`Q8` emits JSON with:

| field | rule |
|-------|------|
| `scene_token` | Echo the requested label |
| `ledger_tail` | Unsigned integer; exact equality required |
| `scalar_near` | Min-image pair-distance sum at final wrapped geometry |
| `addon_aux` | Zero except for `Q5` |
| `wrap_epoch` | `(orbit_crossings * 48271 % 65521) XOR segment_generation` at trial end |
| `refresh_stamp` | Final `nbr_refresh_tag` after the trial horizon |
| `segment_generation` | Count of checkpoint restores during the trial (0 for Q0/Q2, 1 for pause trials) |
| `journal_crc32` | CRC32 over packed `ledger_tail`, `orbit_crossings`, `nbr_refresh_tag`, `segment_generation` |

## Simulation parameters

Six bodies (`kBodyCount`), box edge `11.0`, timestep `0.04`, noise gain `0.37`, pair cutoff on squared distance `36.0` (cutoff_sq seed field `9.0` is unused by pair gather). Scene seeding and velocity initialization live in `driver/integrator_loop.cpp`.

## Trial horizons and checkpoints

Horizon and pause/resume schedules are **fixed per scene token** in `/app/environment/driver/integrator_loop.cpp`. Do not retune `target_steps` or `pause_at` while repairing accounting bugs.

| token | steps | pause/resume at step | continuous run |
|-------|------:|---------------------:|----------------|
| Q0, Q2 | 120 | — | yes |
| Q1, Q3 | 95 | 28 → 29 | checkpoint pair |
| Q4 | 205 | 64 → 65 | checkpoint pair |
| Q5 | 220 | 70 → 71 | checkpoint pair |
| Q6 | 175 | 52 → 53 | checkpoint pair |
| Q7 | 260 | 130 → 131 | checkpoint pair |
| Q8 | 110 | 18 → 19 | checkpoint pair |

Checkpoint trials store segment state at `pause_at`, then restore on the next step. `Q8` runs **fewer** steps than `Q0`/`Q2`; `scalar_near` tracks final geometry after each token's configured horizon, not token index alone.

## Journal replay (`codec_lane/journal_codec.cpp`, CLI in `driver/main.cpp`)

`journal freeze <QTOKEN> <path>` runs a checkpoint trial through its pause step and writes a binary snapshot.

`journal thaw <QTOKEN> <snap> <out.json>` resumes from that snapshot through the trial horizon and emits the same JSON schema as `emit`. Thaw output must byte-match direct `emit` for the same token.

Snapshot serialization uses `JournalSnapshot` in `include/io/journal_tags.hpp`.

## Wrap accounting (`wrap/tile_wrap.cpp`)

`phase_c` folds coordinates into `[0, span)` and counts axis crossings. `crossings_added` must equal the total wrap count for that body on every step. Orbit crossing tally feeds pair-ledger mixing through `orbit_crossings`; suppressing crossings after checkpoint restore poisons ledger, wrap epoch, and journal CRC together.

## Pair ledger (`kernels/pair_ops.cpp`, `measure/bulk_reductions.cpp`)

Each integrator step calls `op_a` with `wrap_stream_tag = orbit_crossings`.

Correct `op_a` behavior:

1. When `segment_latch` is set, clear the latch and reset `post_load_suppress` to zero before evaluating the step — do not skip pair evaluation solely because wrap tags match on the restore step.
2. When `wrap_stream_tag == nbr_refresh_tag` (drift-only refresh) **and** `(lattice_tag & 3) != 0`, skip further ledger work for that step.
3. Otherwise gather min-image pair distances under cutoff, then accumulate:
   - `tag_mix = llround(fp * 1000) XOR (wrap_stream_tag * 1315423911)`
   - `ledger_tail += tag_mix`
   - `nbr_refresh_tag = wrap_stream_tag`
   - `commit_span_fp(state, fp)` where `chunk = (uint64_t)(fp * 4096) XOR (orbit_crossings * 10007)` and `ledger_tail += chunk`

Spurious unconditional increments, extra drift-only branches, or rewritten pair-count shortcuts break exact integer agreement on pause/resume trials.

## Checkpoint restore (`vault/segment_store.cpp`)

`reconcile_b` with `body.dirty == false` snapshots `orbit_crossings` and `ledger_tail` into the segment body. Do **not** bump `segment_generation` on store.

On restore (`body.dirty == true`):

- `orbit_crossings = stored_crossings`
- `ledger_tail = stored_ledger`
- `segment_latch = true`
- `post_load_suppress = 0`
- `nbr_refresh_tag = stored_crossings` (same value as restored orbit crossings, not an offset)
- `segment_generation += 1`

Wrong refresh-tag handoff, generation bumps on store, or nonzero post-load suppression leave drift-only skips, wrap tallies, journal CRC, and wrap epoch inconsistent with the expected path.

## Wrap epoch fold (`session_plane/epoch_fold.cpp`)

`fold_wrap_epoch(orbit_crossings, segment_generation)` must use modulo folding with prime `65521` and salt `48271`, then XOR segment generation. Integer division shortcuts break checkpoint trials even when raw ledger totals look plausible.

## Journal CRC (`codec_lane/journal_codec.cpp`)

`journal_crc32` must include all four packed fields listed above. Omitting `segment_generation` from the CRC input passes continuous trials but fails checkpoint tokens in the delayed-validation gates.

## Scalar near field

After the trial horizon completes, `scalar_near` is the sum of min-image Euclidean distances for all body pairs with squared distance ≤ 36.0, evaluated on positions after a final wrap fold (same min-image convention as pair gather). Longer horizons generally yield larger sums, but shorter tokens such as `Q8` can sit below longer uninterrupted trials.

## Addon auxiliary (`Q5` only)

For mode 5 only, encode final body positions with `stash_encode_tail` over `px[i] * 1.11 + py[i] * 0.01`. All other tokens must emit `addon_aux = 0`.

## Observable ordering hint

After a correct repair, `ledger_tail` strictly decreases from `Q0` through `Q8`. Ordering alone is insufficient — exact per-token integers are required on every field.
