# Matrix output contract

The graded artifact is `/app/output/cmb_out.json`. Rebuild with `/app/environment/scripts/build_lab.sh`, then run:

```bash
/app/bin/mdl_lab --full-matrix --depth 5 --out /app/output/cmb_out.json
```

The checker binary is installed at `/app/bin/mdl_lab` (mirrored at `/app/environment/tools/mdl_lab/mdl_lab`).

## Output schema

Top-level fields:

- `matrix_tag` — string tag, always `cmb_v2`
- `depth_limit` — integer sweep depth used for the matrix run
- `runs` — array of per-scenario rows
- `violation_total` — integer sum of violation rows across all runs
- `cross_digest` — 64-character lowercase hex digest over per-run `digest_hex` values concatenated in matrix run order (never lexicographically sorted)
- `repeat_stamp` — first 16 hex chars of `sha256` over sorted-key JSON (`sort_keys=True`, compact `(',', ':')` separators) of the stamped `runs` array documented below

### Stamped row schema

`repeat_stamp` hashes the `runs` array while each stamped row still includes its `violations` list. Stamp first, then strip `violations` for publication. Each stamped row object includes exactly these fields:

- `codename` — scenario manifest id (`sc_m1` … `sc_m5`)
- `profile` — tick profile label (`strict_tick` or `loose_tick`)
- `digest_hex` — 64-character lowercase hex digest for that scenario/profile sweep
- `violation_rows` — integer count of invariant violation records
- `violations` — array of violation records (`[]` when clean)
- `band_lo` / `band_hi` — integer band bounds (0–255)
- `row_count` — positive row tally for the combo sweep
- `depth_limit` — integer sweep depth applied to that manifest row (per manifest combo-cap rules)
- `event_bytes_len` — length of canonical rebuilt event bytes (payload byte count plus three header bytes)

Published output rows omit only the `violations` array; the other stamped fields remain on each run row.

Each published run row lists:

- `codename` — scenario manifest id (`sc_m1` … `sc_m5`)
- `profile` — tick profile label (`strict_tick` or `loose_tick`)
- `digest_hex` — 64-character lowercase hex digest for that scenario/profile sweep
- `violation_rows` — integer count of invariant violation records
- `band_lo` / `band_hi` — integer band bounds (0–255)
- `row_count` — positive row tally for the combo sweep
- `depth_limit` — integer sweep depth applied to that manifest row
- `event_bytes_len` — length of canonical rebuilt event bytes (payload byte count plus three header bytes)

Local `col_a` / `col_b` in `/app/environment/fixtures/tmp/interim_tally.json` are interim columns only; they are not graded. Text tails under `/app/environment/fixtures/log_txt/` are not graded.

## EVB layout

Authoritative event bytes live under `/app/environment/fixtures/ev_bins/*.evb`. Each file begins with a 12-byte header: magic `EVB\x01`, then one byte each for `mag_seed`, `dur_seed`, `entity_a`, `entity_b`, and `combo_depth`, then three reserved bytes, then the payload. Read at most `combo_depth` payload bytes as activations, reducing each byte modulo 16.

Lane weights used during merge are declared in `/app/environment/docs/lane_coef.json` (`primary`, `secondary`). Tick profiles `strict_tick` and `loose_tick` select the pulse scheduler mode for each matrix row. Settle state lives at `/app/var/lab/settle_state.json`. Operator trail lines append to `/app/var/lab/pulse_journal.jsonl`.

The checker honors `MDL_ENV_ROOT` when set: scenario manifests, docs, and fixtures are read from that tree instead of `/app/environment`. Graded certification still writes `/app/output/cmb_out.json` through `/app/bin/mdl_lab`. Canonical rebuild, pulse scheduling, settle close, and residue persistence are module-level behaviors in the lab sources; graded digests must match those live paths, not a launcher-only wrapper.

## Aura stack merge (exact operators)

Initialize magnitude from `mag_seed`, duration from `dur_seed`, and stack identity from the bitwise XOR of those two seeds.

For the primary rebuild lane, magnitude delta is one plus the remainder of `mag_seed` divided by seven. Duration delta is one plus the remainder of `dur_seed` divided by five. Apply the primary lane weight from `lane_coef.json`.

On merge: add the magnitude delta to magnitude and the duration delta to duration. The new stack identity is the sum of (old stack identity bitwise-XORed with the magnitude delta), the new duration, and the selected lane weight. Omitting the duration term or the lane weight yields a non-contract stack identity.

Canonical event bytes prepend the low byte of the new magnitude, then the low byte of the new duration, then the low byte of the new stack identity, before the unchanged payload. `event_bytes_len` equals that canonical length (payload byte count plus three header bytes).

## Pulse boundary scheduling (exact operators)

For each combo, the scheduler tick is `mag_seed`. The pulse period is the greater of two and two plus the remainder of `dur_seed` divided by five. Pending damage equals the combo length. Iframe active is true when `dur_seed` is odd; overlap ticks equal the remainder of `dur_seed` divided by four.

A boundary exists only when tick is positive and tick is divisible by the pulse period. Off-boundary rows keep the current pending damage, do not fire, and contribute pulse count zero.

On a boundary:

1. When iframe is active **and** overlap ticks are greater than zero, defer: do not fire, set deferred pending to current pending plus the pulse period (not plus one), and contribute pulse count zero.
2. Else when the profile is `loose_tick` and pending damage is greater than the pulse period, defer without changing pending and contribute pulse count zero.
3. Otherwise fire: clear deferred pending, contribute pulse count equal to pending plus one.

Deferral that ignores the overlap-ticks gate, or that advances pending by one instead of by the pulse period, is not contract-correct.

Under `loose_tick`, firing while iframe is active records a `pulse_overlap` violation.

## Lethal settle (exact operators)

Hit points for a combo are:

- side A: max of zero and one hundred minus the combo sum minus (pulse count when not deferred, otherwise zero)
- side B: max of zero and one hundred minus `mag_seed` minus `dur_seed` minus combo length

When both sides are lethal, the winner is the numerically smaller entity id (`entity_a` / `entity_b`), regardless of any action-order array on the manifest. When exactly one side is lethal, that side wins. Mutual-lethal resolution that prefers action-order over the smaller entity id records a `tie_order` violation on combo manifests.

## Combo enumeration

Enumerate breadth-first from the empty prefix. Children visit the first three activations in file order, and the result contains at most one more entry than the applied depth limit, including the empty prefix.

When `scenarios/sweep_m0.json` does not force combo width, non-combo manifests use `min(depth, 3)`; combo manifests use the requested depth.

## Per-combo residue and carry isolation

Each scenario/profile matrix row begins with `pulse_carry` equal to zero, independent of earlier rows. Within a row, after scheduling:

1. Read settle `pulse_carry` (default zero).
2. Residue is the low byte of the sum of that carry, the row's pulse count, and `mag_seed`.
3. Persist the residue as the new `pulse_carry` immediately for the next combo in the same row.
4. Append a journal line with the residue for operator trails.

Witness bytes for a combo are `canonical_event_bytes || residue_byte || combo_bytes`. The combo digest is the lowercase SHA-256 hex digest of those bytes. The run's `digest_hex` is SHA-256 over the concatenation of per-combo digests in **enumeration order** (never lexicographically sorted combo digests).

Settle load must honor the `pulse_carry` field written in `/app/var/lab/settle_state.json`. Journal residue must not overwrite settle `pulse_carry` on load. A stale journal line left after restore must not change graded digests.

## Top-level digests

- `cross_digest`: concatenate each run's `digest_hex` in matrix run order (manifest-major, profile-minor), then SHA-256. Sorting the per-run digests before hashing is not contract-correct.
- `repeat_stamp`: hash the stamped `runs` array (still including `violations`) as compact sorted-key JSON, keep the first sixteen hex characters, then strip `violations` for the published artifact.

## Cleanup and recovery

Destructive cleanup lives in `environment/migrations/cln7.sh`. Bare cleanup poisons settle state (`poisoned` true, `pulse_carry` 255) and truncates the journal. Before re-running the full matrix after cleanup, restore settle bytes with:

```bash
bash /app/environment/migrations/cln7.sh --restore /app/environment/fixtures/seed_store/arena_seed.bin
```

Documented restore must copy the entire seed snapshot into settle state (both `poisoned` and `pulse_carry` as stored in the seed file — do not substitute a hardcoded carry) and clear the pulse journal to empty before the next matrix run. Repeat cleanup without this restore poisons pulse scheduler state consumed by later depth sweeps. After restore, a second process running the same rebuilt binary must reproduce the clean `repeat_stamp`.

## False-green surfaces

Text traces under `environment/fixtures/log_txt/` and the interim tally at `environment/fixtures/tmp/interim_tally.json` may show zero local violation rows for `sc_m1` while the full matrix run still reports violations for later manifests under `loose_tick`. The `--full-matrix` output is authoritative.

## Run order

Matrix rows follow manifest-major, profile-minor order: for each of `sc_m1`…`sc_m5`, emit `strict_tick` then `loose_tick`.
