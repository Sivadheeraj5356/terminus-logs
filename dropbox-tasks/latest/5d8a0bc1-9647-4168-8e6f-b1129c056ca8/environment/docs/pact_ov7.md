# Pact ov7 proof log and matrix contract

## Checker

```bash
/app/environment/bin/og_check --full-matrix --out /app/output/invariant_proof_log.json
```

Build first with `bash /app/environment/scripts/build_all.sh`.

## Arms

Public training arms include `train_a` and `train_b` (slice `kit/blk/tc.mnt`).
Held-out arms include `adv_c` and `adv_d` (slice `kit/blk/td.mnt`).

Each arm emits two rows. The `path_kind` field must be `uninterrupted` or `recovered`.

## Recovery command (idempotent)

```bash
bash /app/environment/migrations/mig_ov.sh --restore-anchors
```

Calling `mig_ov.sh` without `--restore-anchors` clears scratch state and is destructive. The restore form reloads anchors from `kit/seed/arena_seed.bin` into `kit/scratch/anchor.bin` and is safe to repeat. That seed reload is for recovery only; it does not define the scratch contents that remain after a full-matrix run finishes.

## Proof log schema

Root object schema field list

- `schema_id` field must be set to `ov7`
- `instances` field is an array with one object per arm and path_kind (8 rows for the full matrix)

Each instance schema field list

- `arm_id` field means the arm label such as `train_a` or `adv_c`
- `path_kind` field must be `uninterrupted` or `recovered`
- `plan_hex` field means lowercase hex of the 32-byte layer plan
- `seq_hex` field means lowercase hex of the entry sequence bytes
- `guard_trace` field means the 64-char hex digest defined below
- `slice_digest` field means the 64-char hex digest of the mount slice
- `anchor_digest` field means the 64-char hex digest of the 16-byte anchor
- `band_w`, `band_o`, `band_n`, `band_s` fields are integers from the band computation below

## Digests

Let `slice` be the full 64-byte mount slice for the arm.
Let `anchor` be the 16 bytes of `slice` starting at offset 13.
Let `plan` be the 32-byte layer plan.
Let `seq` be the entry sequence bytes.

Digest computation uses sha256

- `slice_digest` is sha256 of `slice`
- `anchor_digest` is sha256 of `anchor`
- `guard_trace` is sha256 of the concatenation `slice` then `plan` then `seq` then `anchor`

Uninterrupted and recovered rows for the same `arm_id` must share the same `guard_trace`.

## Layer plan (32 bytes, little-endian fields)

Each u32 packs four bytes with bit weights at offsets 0, 8, 16, and 24.

```
u32 id_a
u32 id_b
u32 id_c
u32 flags
u32 merge_coord
12 bytes taken from the first 12 bytes of anchor
```

`id_a`, `id_b`, `id_c`, and `flags` are taken from the slice (`flags` at offset 4; ids as u16 at offsets 5,7,9 zero-extended).

`merge_coord` starts as the low byte of `flags`.
When flags bit0 is set (whiteout merge), xor `merge_coord` with the byte at slice offset 4, then xor with `0xa5`.
When flags bit1 is set (opaque), xor `merge_coord` with the byte at slice offset 5, then xor with `0x5a`.

## Entry sequence bytes

```
u16 count
count times u16 slot_index
```

Base order is slots 0 then 1 then 2.
When flags bit1 is set, swap slots 0 and 1 (opacity-first).
When flags bit2 is set and `id_c` is greater than `id_b`, swap the last two slots (sibling hold under nested bind).

## Band fields

Band computation yields integers

- `band_w` adds 17 when flags bit0 is set, else adds 0, then adds (`merge_coord` low byte) modulo 13
- `band_o` adds 19 when flags bit1 is set, else adds 0, then adds `first_slot`
- `band_n` adds 23 when flags bit2 is set, else adds 0, then adds `pair_gap`
- `band_s` is (`id_b` xor `id_c`) masked to 16 bits when flags bit2 is set, else 0

`pair_gap` is the u16 at slice offset 11. `first_slot` is the first `u16` in the sequence after `count`.

## Terminal convergence

After adversarial arms run, plans, sequences, and digests must refresh together. Interim rows in `kit/q9/q9_probe.json` are not authoritative.

After a successful full-matrix run, `kit/scratch/anchor.bin` must hold the 16-byte `anchor` of the arm last processed (the 16 bytes of that arm's mount slice starting at offset 13).
