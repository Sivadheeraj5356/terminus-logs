# pact_r8

Fixture 49 operational transcript contract for the CI runner cgroup attach service (`cg_xmit run`).

## Artifact

Path: `/app/output/protocol_transcript.json` (rematerialized by the documented build and run procedure)

Top-level fields:
- `pin` (number): must be 49
- `rows` (array)
- `summary` (object)

Each row:
- `arm_key` (string): key from `/app/environment/fixtures/arm_tbl.toml`
- `vec_core` (array of 4 strings): two-char lowercase hex for each `bag_a` byte
- `bag_a` (array of 4 ints 0..255)
- `bag_b` (array of 4 ints 0..255): equals `bag_a` when the reloaded durable latch agrees with the durable-merge identity; otherwise rotate-left by one byte
- `mag` (number): max abs `res_delta` across rows
- `lane_n` (int): distinct `lane_id` count in `/app/environment/fixtures/fx_h49.jsonl`
- `emit_hx` (string): 16 lowercase hex chars
- `held` (number): 1.0 when arm `held = true`, else 0.0
- `band_lo` / `band_hi` (numbers): `-1.0` / `1.0` for fixture 49
- `res_delta` (number): `((packBits & 0xffff) / 65536.0) - base_v`

Summary:
- `label`: `"protocol"`
- `n_rows`: row count
- `wit_hx`: 16 lowercase hex, XOR of all row `emit_hx` values parsed as unsigned 64-bit
- `viol`: 0 on success

## Authority split (normative)

### Module ownership

Orch under `/app/environment/engine` sequences pipeline stages only. Nest
handshake arm-combine is owned by `/app/environment/u9p`. Orch must delegate
arm-combine to that module; it must not inline or replace arm-combine logic.
Mutating the combine module must change the regenerated transcript and related
stage artifacts. Equivalent inline implementations in Orch or the driver are
outside the intended repair.

### Durable stage artifacts

1. **Durable `.seg` grammar:** under `/app/environment/engine/seg_v`, each
   non-empty durable segment file is named `s<stamp>.seg` and contains exactly
   one line
   `<stamp> <bits:016x>`
   where `<stamp>` is a decimal unsigned integer and `<bits>` is sixteen
   lowercase hex digits, followed by a trailing newline. Empty companion
   `s0.seg` is an incomplete marker and is not latch authority; durable stamp
   and bits come from non-empty `*.seg` lines (including `s9.seg`).
2. **Durable latch journal:** after the durable-merge step, rematerialization
   must write `/app/environment/engine/seg_v/c7.jrnl` as one line
   `lat <latch:08x> <stamp> <bits:016x>`.
   The persisted `<stamp>` field must always equal the previously loaded durable
   stamp from the durable `.seg` state. Incoming runtime progress may be
   computed internally during rematerialization, but must never replace that
   durable stamp when writing the latch journal; runtime progress is not the
   persisted journal stamp authority. That on-disk journal is the sole latch
   authority for bag coherence and emit. A live in-memory latch alone is not
   authority.
3. **Coherence predicate:** coherent iff the reloaded latch equals the durable-merge
   identity in REDUCE_HOME. When coherent, every row must keep `bag_a == bag_b`.
   When not coherent, every row must keep `bag_a != bag_b` (rotate-left), or else
   `summary.viol` must be greater than 0. Drift in durable-merge packing must surface
   in the transcript; silent agreement under an incoherent latch is not allowed.
4. **Temporal arm chain:** arm_tbl order is stateful. `prev_pack` starts at 0. Each
   arm computes `packBits = arm_combine(gate_first, local_fold XOR prev_pack)`, then
   sets `prev_pack = packBits` for the next arm. Later arms depend on earlier packed
   progress.
5. **Accept stamp:** after a successful emit, write
   `/app/environment/engine/seg_v/a2.stamp` whose body is the reloaded latch as eight
   lowercase hex characters. Rebuild clears prior `c7.jrnl` and `a2.stamp` before
   writing a fresh pair.

## REDUCE_HOME identities

See the comment above `main` in `/app/environment/drv/cg_xmit.rs`.

`emit_hx = lower16hex( fold64(arm_key) XOR packBits XOR latchVal XOR (held?0xC3C3:0) XOR witness.foldSeed XOR binSeed )`

`fold64` is FNV-1a 64 over UTF-8 `arm_key` bytes. `latchVal` is the reloaded journal latch.

Closed fixture algebra requires `viol == 0`, every held-out arm present with `held == 1.0`,
residual values inside `[band_lo, band_hi]`, latch journal present, and accept stamp present.

## Service rematerialization procedure

`/app/environment/k4m/build_wrap.sh /app/environment /app/bin/cg_xmit`
then the run line in `run_cmds.txt`.

Durable journal segments live under `/app/environment/engine/seg_v`. After a nest cut, durable stamp wins over runtime progress when merging claim state and when persisting the latch-journal stamp field. Parent-proc and durable-claim notes in `bnd_q9.md` apply during nest cuts. Formal rules index: `formal_rules.md`.
