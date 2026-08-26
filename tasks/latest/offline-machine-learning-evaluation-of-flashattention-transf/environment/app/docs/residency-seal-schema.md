# Residency seal schema

## Binary ledger `/app/data/residency.bin`

If the ledger path is **missing**, loaders for `kvtile-plan`, `kvtile-advance`, and `kvtile-seal` treat residency as empty (zero pages). Seal then exits **2** with no JSON write; advance still runs against that empty state and exits **0** after persisting (see `/app/docs/cli-reference.md`).

Little-endian layout:

- magic `KVT1` (4 bytes)
- `u32 run_epoch`
- `u32 page_count`
- `u32 free_stack_len`
- `u32 n_map` then `n_map` pairs of `u32 logical` / `u32 physical`
- `free_stack_len` × `u32` free page ids (LIFO top at the end)
- `u32 n_heads` then per-head `f64 m` and `f64 ell` (IEEE)
- trailing `u32 tiles_planned`, `u32 mask_bits`, `u32 compact_gen` (successful compact count; default 0), `u32 visit_checksum` (XOR custody of mask-kept schedule visits; default 0 when absent on legacy short trails), `u64 merkle_tip` little-endian (parent-chained tip; default 0 when absent), `u64 residue_u64` little-endian (residue ouroboros; default 0 when absent)

### schedule witness `/app/data/schedule.mir`

After a successful plan, the evaluator writes a binary schedule mirror at `/app/data/schedule.mir`:

- magic `SCH1` (4 bytes)
- `u32 visit_count` little-endian
- `visit_count` triples of `u32 h`, `u32 qi`, `u32 kj` little-endian in the same mask-kept visitation order used for `visit_checksum`

`schedule_crc` is the IEEE CRC-32 (poly `0xEDB88320`, ZIP/PNG family) of the **on-disk mir bytes**. If the file is missing or unreadable at seal time, `schedule_crc` is `0`. Seal folds the decimal `schedule_crc` into `seal_digest`. Replan overwrites the mir; agents that only fold `visit_checksum` without reading the mir bytes fail independent recompute.

### residue_u64 (ouroboros with tip)

`residue_u64` is a `u64` custody chain:

- At plan: `residue_u64 = ((visit_checksum as u64) << 32) | (mask_bits as u64)`.
- After each successful advance has updated `merkle_tip`: `residue_u64' = rotate_left(residue_u64, 7) XOR merkle_tip XOR (((run_epoch as u64) << 32) | (compact_gen as u64))`.

Plan reseeds residue; advance must parent-chain after tip update. Seal folds decimal `residue_u64` after `schedule_crc`. Leaving residue at the plan seed after a non-zero advance, or omitting the field from the pipe, fails recompute.

## JSON seal `/app/output/kvtile-residency-seal.json`

Top-level key order (must match exactly when written):

1. `seq_id` (string)
2. `run_epoch` (integer)
3. `tiles_planned` (integer)
4. `pages_resident` (integer)
5. `mask_bits` (integer — count of 1-bits in packed_mask)
6. `m_stats` (array of decimal strings)
7. `ell_stats` (array of decimal strings)
8. `seal_digest` (64 lowercase hex chars)

### seal_digest payload

UTF-8 concatenation **without trailing newline**:

`seq_id|run_epoch|pages_resident|` + physical page ids of currently mapped entries joined by `,` in **ascending logical key order** (sort the map by logical id, then emit each entry’s physical id — do **not** re-sort by physical id) + `|` + `mask_bits` + `|` + `m_stats` joined by `,` + `|` + `ell_stats` joined by `,` + `|` + `prior_fold` + `|` + `compact_gen` (decimal, no leading zeros beyond the number itself) + `|` + `visit_checksum` (decimal u32) + `|` + `merkle_tip` (decimal u64) + `|` + `compiler_epoch` (decimal u64) + `|` + `rebuild_nonce` (decimal u64) + `|` + `schedule_crc` (decimal u32 IEEE CRC of `/app/data/schedule.mir` bytes, or `0` if missing) + `|` + `residue_u64` (decimal u64)

Then SHA-256 hex digest of that UTF-8 byte string (cryptographic seal of residency state — not a field-map dump).

`compact_gen` is the ledger counter of successful densifying compacts (block-table-contract.md). A seal that omits it or uses a stale value after compact fails independent recompute. LIFO free-stack reuse on replan remaps logical→physical without changing the page set; logical-order emission makes that remapping visible in `seal_digest`.

### compiler_epoch + rebuild_nonce (build-time ouroboros)

`/app/scripts/build.sh` (presence check) and `/app/scripts/rebuild.sh` (full cargo rebuild) must (re)write `{KVTILE_APP_ROOT}/var/compiler-epoch.json` as a single JSON object:

`{"epoch_u64": <u64>, "rebuild_nonce": <u64>}` (optional trailing newline).

Compute:

`epoch_u64 = first 8 bytes of SHA-256(UTF-8("kvtile-compiler-epoch|" + decimal_spine_salt))` interpreted as a **big-endian** `u64`, where `decimal_spine_salt` is the profile `spine_salt` field with no leading zeros beyond the number itself (e.g. `0` when unset).

`rebuild_nonce` combinatorial rule:

- After **`/app/scripts/rebuild.sh`** (cargo install path): `rebuild_nonce = first 8 bytes BE of SHA-256(UTF-8("kvtile-rebuild-nonce|" + decimal_epoch_u64))`.
- After **`/app/scripts/build.sh`** (binary presence check only): `rebuild_nonce` must be **`0`**.

At seal time, load both fields from that file when present; if the file is missing or unreadable, fold `0` for each. A seal that omits `|compiler_epoch` or `|rebuild_nonce` from the payload, folds a stale epoch after rebuild rewrote the file, or folds `0` for `rebuild_nonce` when rebuild wrote a non-zero nonce, fails independent recompute.

Candidate evaluator binaries must not read verifier reference trees (e.g. under `/opt/kvtile-verifier`); seal/epoch logic belongs in `/app` only.


### visit_checksum (ouroboros custody)

`visit_checksum` is a `u32` XOR fold computed during `kvtile-plan` while walking the tile visitation order. Initialize `acc = 0`. For every head `h` and every mask-kept `(qi, kj)`, update:

`acc ^= ((h << 16) | (qi << 8) | kj) & 0xffffffff`

Persist `acc` as the trailing `visit_checksum` in `residency.bin`. Advance must preserve it. Seal folds the ledger’s `visit_checksum` into `seal_digest`. Plan recomputes it from the current pack (replacing any prior value). Wrong visitation filters (unique-kj undercount or unmasked overcount) desync both `ell_stats` and `visit_checksum`.

### prior_fold (ouroboros)

`prior_fold` is the first 16 lowercase hex characters of `SHA-256(UTF-8(prior_material))` where:

- If `{KVTILE_APP_ROOT}/var/prior_seal.hex` exists (default root `/app`) and contains a 64-char lowercase hex digest, `prior_material` is that file’s contents (trimmed, no newline).
- Otherwise `prior_material` is exactly sixty-four ASCII `0` characters.

After a successful seal write, the implementation must overwrite `{KVTILE_APP_ROOT}/var/prior_seal.hex` with the new `seal_digest` (64 hex chars, no trailing newline).

`kvtile-plan` must delete `{KVTILE_APP_ROOT}/var/prior_seal.hex` when present so a fresh plan restarts the fold chain at the zero-material baseline.


### merkle_tip (parent-chained spine)

`merkle_tip` is a `u64` folded on every successful `kvtile-advance` after map mutations. Initialize at plan as `0`. After advance updates `run_epoch`, optional releases, and optional densifying compact, recompute:

`merkle_tip' = first 8 bytes of SHA-256(prior_tip_be8 || run_epoch_be4 || compact_gen_be4 || phys₀_le4 || phys₁_le4 || …)` interpreted as a big-endian `u64`, where `physᵢ` are physical page ids of currently mapped entries in **ascending logical key order** (same order as the seal page list).

`prior_tip` is the ledger’s previous `merkle_tip`. Persist `merkle_tip` as the trailing little-endian `u64` on `residency.bin`. Seal folds the decimal tip into `seal_digest`. Plan resets tip to `0` after trailer validation.

### spine trailer (ouroboros gate)

`attn-profile.json` field `spine_salt` is a `u64`. After a successful seal, write `{KVTILE_APP_ROOT}/var/spine_trailer.hex` as exactly 16 lowercase hex digits encoding `(merkle_tip XOR spine_salt)` with no newline.

Before `kvtile-plan` mutates a loaded ledger (LIFO free/reallocate), if `spine_trailer.hex` exists it must decode to that XOR mark for the ledger’s current tip and profile salt; otherwise plan exits non-zero. After a successful plan, delete the trailer file and reset `merkle_tip` to `0`.
