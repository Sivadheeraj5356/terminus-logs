# Verification contract

Auth session authority checks. Violations are privilege and authentication faults, not generic build errors.

## Clock composition

Profile constants include abs_lifetime and idle_lifetime. Absolute deadline is issued_at plus abs_lifetime and must stay frozen under idle soft refresh. Idle deadline is last_activity plus idle_lifetime. Field `composed` reports the earlier of those two deadlines. Field `abs_deadline` is graded on terminal rows.

After the `clock_mix` soft-refresh chain (1020, 1040, 1090, 1600) both profiles must report `composed` equal to the frozen absolute deadline (tight 1100, loose 1500). Idle refresh must not raise `abs_deadline`.

## Circulation fence

After a seal for generation G, durable latch state must report synced_gen matching G before any admit for G is legal. Prior generations must not remain admit-capable after rotation, including back-to-back seals and skipped generation numbers. Field `dual_peak` is the maximum dual-valid observation across the bundle steps and must be zero on success for `circ_fence` and `rot_chain`. Bundle `circ_fence` ends at generation 4 after a skipped-gen seal. Bundle `rot_chain` advances generations 1→2→3 with admits under the synced fence and a stale-fence reject.

## Occupancy fencing

Occupancy fold changes must carry a fence counter matching the latch-synced generation. Admit and reclaim under the same fence must keep occupancy at or below field `limit`, which equals profile burst_cap for the principal RBAC session budget. Bundle `burst_cap` seats occupancy matching `limit` after the surge. Bundle `rot_chain` ends with occupancy 3 under both profiles after three successful admits and one stale reject. Stale-fence ops are rejected. Over-budget admits must not apply.

When `/app/output/recovery.marker` reads `ok`, the checker applies a reload-hold touch on `burst_cap` before packing the row. Fold must clear that hold without wiping the occupancy accumulated by the surge.

## Epoch ledger

Each matrix run writes `/app/output/epoch.ledger` with one line per profile/bundle capturing gen, synced_gen, dual flags, occupancy, and abs_deadline. With profiles tight and loose and four bundles, a healthy ledger has exactly 8 data rows. A second identical run must report meta `epoch_ok` as `ok` when lines match. After ledger corruption, re-running the matrix must rewrite a coherent ledger from the live authority model; a following run must again report `epoch_ok` as `ok`.

## Witness schema

Terminal `/app/output/witness.json` is graded. Top-level keys are matrix, profiles, rows, digests, and meta. Each journal row carries bundle, profile, gen, synced_gen, dual_valid, dual_peak, status, composed, abs_deadline, occupancy, limit, digest_key, digest_sha256, and journal_tag (14 fields). Stage JSON under `/app/output/stage/` omits digest_sha256 and journal_tag and therefore has fewer keys. Meta `journal_field_count` must equal the journal row key count; meta `stage_field_count` must equal a stage object key count; journal count must exceed stage count. Meta also carries recovery_marker and epoch_ok.

Digests use SHA-256 over canonical bytes in `/app/environment/samples/raw_bytes/`. journal_tag is the first eight hex characters of SHA-256 over digest_sha256, a pipe, profile, a pipe, and bundle.

## Module probes

Grading compiles verifier-owned probe drivers with `g++` against the static authority libraries under `/app/build` produced by `build_all.sh`. Those probes must exit 0 after a correct harden (seal rotation closes dual-valid, compose keeps absolute deadline frozen, quota seats occupancy through reload-hold). Checker-only patches that leave the libraries buggy will fail probe grading.

## Destructive migration / recovery

`/app/environment/migrations/v2_hold.sh` moves raw samples behind a hold marker. Idempotent recovery from `/app` uses

```bash
/app/environment/migrations/v2_hold.sh --recover
```

Recovery restores `/app/environment/samples/raw_bytes/` and writes `/app/output/recovery.marker` with body `ok`. Re-running `--recover` is a no-op when samples are intact.
