# CLI reference

## `kvtile-plan --pack <path> --profile <path>`

Loads a `.kvpack` sequence pack and profile. Writes `{KVTILE_APP_ROOT}/data/residency.bin` (default root `/app`). When a prior **valid** KVT1 ledger exists, releases every mapped page onto the free stack (preserving high-water `page_count` and `compact_gen`) then reallocates required logicals via LIFO reuse; corrupt or missing ledgers start empty. Validates `{KVTILE_APP_ROOT}/var/spine_trailer.hex` against `merkle_tip XOR spine_salt` when present (stale mark → non-zero exit), then sets `run_epoch` to `0` and `merkle_tip` to `0`, deletes prior_seal and spine_trailer, updates online-softmax stats from tile windows, and persists the ledger. Exit 0 on success.

## `kvtile-advance --profile <path> [--compact] [--release-logical <id>]…`

Loads `{KVTILE_APP_ROOT}/data/residency.bin`. A **missing** ledger file is treated as an empty residency (default empty map, `pages_resident == 0`, `run_epoch == 0`, `compact_gen == 0`) — not a hard failure. Increments `run_epoch` on that in-memory ledger. Optional `--release-logical` (repeatable) frees those logicals onto the LIFO free stack without allocating. With `--compact`, applies densifying compact when `free_ratio > compact_threshold` (increments `compact_gen` on success). Then folds `merkle_tip` per residency-seal-schema.md. Persists the ledger to `{KVTILE_APP_ROOT}/data/residency.bin`. Exit **0** on success (including when the file was missing and the empty ledger was advanced). Exit **1** on other failures (bad profile, I/O errors after a present-but-corrupt file, etc.).

## `kvtile-seal --seq-id <id> [--out <path>]`

Loads `{KVTILE_APP_ROOT}/data/residency.bin`. A **missing** ledger file is treated as an empty residency (`pages_resident == 0`) — same empty baseline as advance. File-not-found is **not** a hard error for seal; it is equivalent to `pages_resident == 0`. If `pages_resident == 0` (missing file **or** empty/planned-empty ledger), exit **2** and do not write seal JSON. Otherwise writes the seal JSON to `--out` (default `{KVTILE_APP_ROOT}/output/kvtile-residency-seal.json`), folding `prior_fold`, `compact_gen`, `visit_checksum`, and `merkle_tip` per residency-seal-schema.md, then persists the new `seal_digest` into `{KVTILE_APP_ROOT}/var/prior_seal.hex` and writes `spine_trailer.hex` as `(merkle_tip XOR spine_salt)`. Exit **0** on success. Exit **1** on other failures.

Harness rebuild: `/app/scripts/build.sh` (presence check + writes `/app/var/compiler-epoch.json` with `rebuild_nonce` **0**). Agent source rebuild: `/app/scripts/rebuild.sh` (cargo then same epoch file with non-zero `rebuild_nonce`). When `KVTILE_VERIFIER_EPOCH_ONLY=1`, `rebuild.sh` only refreshes the epoch file without cargo. Seal folds both `compiler_epoch` and `rebuild_nonce` per residency-seal-schema.md. Candidate binaries under `/app/bin` must not depend on files under `/opt/kvtile-verifier`.
