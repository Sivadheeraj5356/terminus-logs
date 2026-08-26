# Sccache build-cache attestation contract

## Deliverable

`/app/output/kq_report.json` is the build-cache SBOM-style attestation: `cache_digest` plus `rows`. Each row has `scenario`, `view`, `key`, `generation`, `hash_count`.

Public scenarios `base_a`, `base_b`, `base_c` must preserve their deck generations (dependency lock pins). Scenario `fork_f1` is an in-deck authority split. `reload_r1` exercises lockfile dependency-tier reload. `native_n1` exercises native witness bands on the compiler stub.

## Build-cache pipeline

1. Lock resolvers read sccache deck bytes and write `/app/output/kq_frames.ndjson` (one JSON object per line).
2. Ingest also writes `/app/output/kq_auth.bin` for auth-lane closure.
3. The attestation exporter (`zen_e`) reads frames plus auth lane and emits the report, staging ledger, and reproducibility digest.

Attestations must flow through frame ingest → export. Skipping the frames artifact breaks digest closure and the release guard.

## Frame kinds

Frames use `kind` values `scope`, `argv`, `define`, `wrap`, `native`, `epoch` (meta). Export maps them to report views `scope`, `argv_text`, `define_trace`, `wrapper_hash_bin`, `witness`, plus derived `ledger_bind`.

Argv frames carry the source record status in `flags`.

## Authorities

Argv authority sums hash counts from argv frames whose `flags` are **1 (active)** or **2 (phantom)**. Only `flags == 1` frames become `argv_text` rows; phantom frames contribute to authority and ledger math only.

Wrapper authority comes from `molt_b(..., 2)`. KQWH segment headers include a mode byte after the entry count: when bit 0 is set, wrapper authority is the **maximum** segment hash count; otherwise it is the **sum**.

When argv and wrapper authorities disagree, emit `witness` / `band_reconcile` with round-half-up average: odd sums use `(argv + wrap + 1) // 2`, even sums use `(argv + wrap) // 2`.

Every non-control scenario gets `ledger_bind` / `bind` via `bind_h`. Per-scenario inputs are argv authority, wrapper authority, define tick sum, and scope tier from that scenario's frames. Shared inputs are deck `epoch`, the uint16 `auth_lane` read from `/app/output/kq_auth.bin`, and `frame_count` — the total ingested frames whose scenario is not `_meta` (same count for every scenario). Closed as:

`(argv_hc * 7 + wrap_hc * 11 + def_sum + epoch * 13 + scope_tier * 3 + (auth_lane * 5) % 241 + (frame_count % 17) * 3) % 241`

## Auth lane (ingest)

During ingest, accumulate `base_a_argv_authority` as the sum of argv frame `value` fields for scenario `base_a` (active and phantom argv records). Set `base_a_wrapper_authority` to the wrapper head aggregate from `molt_b(..., 2)` on `base_a`'s wire.

After all frames are written, emit `/app/output/kq_auth.bin` as a little-endian uint16:

`auth_lane = (base_a_argv_authority XOR base_a_wrapper_authority XOR (epoch * 31)) & 0xffff`

where `epoch` is the integer in the deck's `epoch.txt`. Export (`zen_e`) reads this seal when evaluating `bind_h`.

## Argv status gate

Scenario `argv_status` must be exactly `nominal` for argv wire decode. Non-nominal statuses suppress argv frames for that scenario without affecting define-order or wrapper ingest.

## Reload scope (dependency lock tiers)

Without `--reload`, scope comes from the YAML rank file's highest-tier token. `scope_hash` is **`len(effective_token)` only** — do not add the tier index on the YAML path.

With `--reload` (CLI flag or scenario `reload: true`), deck `*_resp.rsp` files override YAML by tier precedence (highest tier wins among non-empty `*_resp.rsp`). On this reload path, `scope_hash` is **`len(effective_token) + tier`** where `tier` is the winning rsp tier.

The scope frame stores `scope_hash` in `value` and the active tier in `flags`.

## Define-order dependency pins (KQDT)

Blobs begin with magic `KQDT`. Header flags are the little-endian uint16 at bytes 9–10 (1-based indexing). Flag bits select layout and scaling:

| Bit | Value | Effect |
|-----|-------|--------|
| 0 | 1 | Permuted record layout: `sentinel`, `key_len`, `key`, `tick` (canonical order is `tick`, `sentinel`, `key_len`, `key`) |
| 1 | 2 | Scale ticks: `tick // 8` before further normalization |
| 2 | 4 | After fold, apply tighten: subtract 1 from each tick (minimum 1) |

Per-record sentinel byte: when sentinel is `1` and the tick is positive, apply `tick % 512` after flag scaling.

**Total-budget fold:** After per-record normalization, let `total = sum(eff_tick)`. When `total > 512`, apply proportional fold — not per-entry capping. Apply tighten last when flag bit with value 4 is set.

## Argv / wrapper wires

Argv records are length-prefixed with a checksum footer that mixes the body and the record count. Wrapper segments begin with magic `KQWH`. Validate and decode from the bundled wires.

## Checksum (argv body)

`(sum(body_bytes) + nrec * 17) & 0xffffffff`

## Denylist gate

When `KQ_DENYLIST` points at JSON with `blocked_keys` and `required_width`, suppress argv ingest only when the active argv wire byte length equals `required_width`. Define-order decode is never denylisted.

## Staging and reproducibility digest

Export stages report rows plus **staging-only** control wraps to `/app/output/kq_stage.ndjson` as CSV lines:

`scenario,view,key,generation,hash_count`

`control_empty` wraps appear in staging (and therefore in `cache_digest`) but are excluded from `/app/output/kq_report.json` rows. Include `ledger_bind` rows in staging. Recompute `cache_digest` from the staged lines so offline rebuilds are bit-identical:

`sha256` over sorted `scenario,view,key,generation,hash_count` lines joined by newline (trailing newline).
