# Output contract

From `/app/environment`, run `cargo build --release --bins --manifest-path /app/environment/Cargo.toml`, then `/app/bin/run_chainlab`, which loads `/app/data/rotation_spec.txt` before writing outputs. If that file is absent, `run_chainlab` must exit with failure rather than emit a static trace bundle. Release build artifacts land under `/app/target/release/`. The stock image keeps `cargo` on `PATH` at `/usr/local/cargo/bin/cargo`. Grading cross-checks live slices via `/app/target/release/probe` (`TB_PROBE` modes include cold, bind, consult, row, wire, dual, frame, and over_ticks).

## `/app/output/trace.json`

Top-level `cases` array. Each case has `tag`, `blk_marks` (unsigned integer generation samples), and `tries`.
Each try includes `wire_tag`, `carry_at_try`, `latch_denied`, and `key`.

Path refusal is a single-bit outcome derived from link carry, consult key, and the active gate slice byte (default 1 from the unit gate profile unless overridden in rotation_spec for cold_tick). Consult derives `latch_denied` from link carry, consult key, and the active gate slice byte (default 1 from the unit gate profile unless overridden in rotation_spec for cold_tick). Flipping key at fixed carry toggles refusal.

`link_ticks` `blk_marks` must follow the tick pairs declared in `rotation_spec.txt` through live generation peaks, not self-referential JSON. The first sample in a frame must reflect only ticks within that frame, not peaks carried from a prior reload frame.

## `/app/output/readout.csv`

Columns: `tag`, `latch_denied`. Each row mirrors the final try refusal for that tag under the harness pulled view.
When mapping a row to CSV, `latch_denied` must follow the harness `View.pulled` bit for that tag.

## Rotation tick and link semantics

- Each rotation tick pair `(a, b)` extends `ctx.acc` with the wrapping sum `a + b`.
- After each tick, sample `blk_marks` from the shared generation peak, which must advance to the strict maximum of the prior peak and `ctx.acc` (CAS loop semantics: larger published values raise the peak; the peak never retreats). A single tick with operands `(a, b)` leaves the peak at `a + b` when `ctx.acc` started at zero; larger operand pairs raise it further across multi-tick chains.
- Link tokens must carry the live generation value at link time: the greater of session carry, link operand `q`, and the current generation peak. When `q` is sourced from the live peak (`TB_BIND_Q=0` in probe replay), link carry equals that peak — not session carry alone and not an xor mix of link parameters alone.

## Case reload frames

The driver opens and closes a reload frame around each bundled case. Frame open must zero the shared generation peak before ticks in that case. Frame close records the peak reached in the case; the next frame open must not seed the peak cell from that recorded tail.

## Cross-case invariants

- `cold_tick`: lone try `carry_at_try` equals the sole `blk_marks` entry. Optional per-case `gate_slice` in `rotation_spec.txt` overrides the unit gate slice byte for path refusal on that case.
- `link_ticks`: at least two strictly increasing `blk_marks` samples; final try `carry_at_try` equals `blk_marks[-1]`. Editing `link_ticks.bumps` in `rotation_spec.txt` must change `blk_marks` on rerun without rewriting `cold_tick` samples.
- `rotate_hold`: final try `carry_at_try` is strictly below the post-rotation generation peak (held link minted before the rotation tick).
- `twin_leaf`: `int(tries[0]["carry_at_try"]) < blk_marks[0]` and `int(tries[-1]["carry_at_try"]) == blk_marks[-1]`.

## Diagnostic probe

Rebuild `/app/target/release/probe` with the driver. The probe prints one stdout line per invocation (`1`/`0` for booleans).

| `TB_PROBE` | Output | Env vars |
|------------|--------|----------|
| `cold` | final generation peak after one tick | `TB_BUMP_A`, `TB_BUMP_B` |
| `bind` | link-token carry after tick + link | `TB_BUMP_A`, `TB_BUMP_B`, `TB_SEED`, `TB_BIND_P`, `TB_BIND_Q` (`0` uses live peak as `q`) |
| `consult` | path refusal bit | `TB_CARRY`, `TB_KEY`, optional `TB_GATE_SLICE` |
| `row` | CSV row denial bit | `TB_PULLED`, `TB_TEXT_A`, `TB_TEXT_B` |
| `wire` | `peak,carry` for rotate_hold pattern | (fixed scenario) |
| `dual` | `carry,peak` for twin_leaf first wire | (fixed scenario) |
| `frame` | `ticks_a\|ticks_b` across a close/open pair | optional `TB_FRAME_A`, `TB_FRAME_B` bump chains like `3,1;5,2` |
| `over_ticks` | comma-separated `blk_marks` ticks | optional `TB_BUMP_CHAIN` like `3,1;5,2;7,1` |

Use probe slices to learn expected rotation, link, consult, row, and frame behavior before trusting regenerated `trace.json` / `readout.csv`. Divergence between `run_chainlab` artifacts and probe replay means some shared rotation, link, consult, row, or reload path no longer implements the contracts above.
