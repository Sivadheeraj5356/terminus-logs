# Content-addressed CDC vault (v3)

Implement from scratch in Go under `/app`. No starter sources. Produce `/app/bin/backup-dedup` from `/app/main.go` and `/app/go.mod` via `/app/run.sh` with `CGO_ENABLED=0`, standard library only, and `GOPROXY=off`. Exit 0 with empty stdout and stderr. Do not modify `/app/data/` or `/app/spec/`. Identical inputs must yield byte-identical outputs.

## Remote policy material

Read `/app/data/endpoints.json` with fields `policy_material_url` and `policy_material_sha256`. Before any job:

1. HTTP GET the URL and take the full response body.
2. Abort unless lowercase hex of `SHA-256(body)` equals `policy_material_sha256`.
3. Derive:
   - `attestation_domain` = first 32 hex characters of `SHA-256(body)`
   - `gear_seed` = `SHA-256("gear\0" || body)` (32 bytes)
   - `mac_key` = `SHA-256("hmac\0" || body)` (32 bytes)
   - `store_salt` = `SHA-256("store\0" || body)` (32 bytes)
4. Write `/app/output/policy_receipt.json` with keys in this order: `url`, `sha256`, `byte_length`, `attestation_domain`, `gear_seed_hex`, `store_salt_hex`, `mac_key_hex`.

`gear_seed_hex`, `store_salt_hex`, and `mac_key_hex` are lowercase hex of the 32-byte values. `byte_length` is the body length as a JSON number.

Internet access is required for the fetch.

## Manifest and job configs

`/app/data/manifest.json`: `{ "version": 1, "jobs": [ { "id", "src", "config" } ] }` with paths relative to `/app/data/`. Process jobs in array order.

Each `backup_config.json`:

```
{ "exclude": ["glob", ...], "gzip_level": 1|6|9 }
```

A job is **failed** when the scanned set of non-excluded paths is empty: emit a `report.jsonl` row with `status` `"failed"`, null metrics, and no `/app/output/jobs/<id>/`.

A job is **quarantined** when any non-excluded relative path contains the substring `__deny__`: `status` `"quarantined"`, null metrics, no job directory, omitted from the ledger.

## Walk rules

- Walk with `Lstat`. Never follow symlinks.
- Relative paths use `/` separators, no leading `./`.
- Apply each exclude pattern with Go `path.Match` against the full relative path and against the final path segment.
- Classify:
  - `symlink` for symbolic links (record target via `Readlink`; no body chunks)
  - `hardlink` when another already-scanned path shares `(dev, ino)` and is not a symlink; the **primary** of an inode group is the shallowest path (fewest `/`), ties broken by lexicographically smallest path; non-primaries reference the primary and share its chunk list
  - `regular` otherwise for normal files (including the primary of a hardlink group)

## Content-defined chunking

Build a 256-entry `uint32` gear table from `gear_seed`:

```
gear[i] = big-endian uint32 of SHA-256(gear_seed || u32be(i))[0:4]
```

Fingerprint for the current chunk starts at `0`. For each input byte `b`:

```
fp = ((fp << 1) + gear[b]) mod 2^32
length += 1
```

Constants: `min_chunk = 3072`, `max_chunk = 12288`, `mask = 0x1FFF`.

After each byte: force a cut when `length >= max_chunk`; otherwise cut when `length >= min_chunk` and `(fp & mask) == 0`. After a cut, append the chunk bytes, reset `fp` to `0` and `length` to `0`. After the final byte, emit any remaining bytes as one chunk (may be shorter than `min_chunk`).

Empty regular files produce `"chunk_ids": []` and no store objects.

For each non-empty chunk:

- `chunk_id` = lowercase hex of `SHA-512/256(chunk)` (64 hex characters). Use Go `sha512.Sum512_256`.
- `store_name` = lowercase hex of `SHA-256(store_salt || chunk)`.
- Write bytes once to `/app/output/chunk_store/<store_name[0:2]>/<store_name>` if absent.

## Whole-file and cross-job dedup

`file_id` = lowercase hex of `SHA-512/256(full file bytes)` for regular files and hardlink aliases (aliases inherit the primary's `file_id`).

Identical file bytes across jobs share the same `chunk_ids` and must reuse existing `/app/output/chunk_store/` objects (first write wins). Hardlink aliases within a job increment `ref_count` for each shared `chunk_ids` slot but do not write additional store objects.

`ref_count` in a job's `chunk_catalog.json` counts every `chunk_ids` slot in that job only (including hardlink aliases). `global_chunk_registry.json` accumulates `ref_count` across all successful jobs.

## Sparse holes

Within each regular/hardlink primary body, any maximal run of `0x00` bytes of length `>= 2048` is a hole. Record holes in `restoration_map.json` as `{ "offset", "length" }` (byte offsets into the logical file). The tar archive member still stores the fully expanded byte content (holes included as zeros).

## Per-job Merkle root

Take the unique `chunk_id` values from that job's catalog, sorted lexicographically.

- Empty set → `merkle_root` is 64 zero hex digits.
- Leaf = `SHA-256( 0xA5 || ASCII(chunk_id) )`.
- Parent = `SHA-256( 0x5A || left || right )` where `left` and `right` are raw 32-byte digests.
- At each level, if the node count is odd, promote the last node alone (do not duplicate).
- `merkle_root` = lowercase hex of the final digest.

## Attestation

For each successful job write `/app/output/jobs/<id>/attestation.json` with keys: `job_id`, `merkle_root`, `domain`, `manifest_sha256`, `store_binding`, `signature_hex`.

- `domain` = `attestation_domain` from the policy receipt.
- `manifest_sha256` = lowercase hex `SHA-256` of the exact bytes of `/app/output/jobs/<id>/manifest.json`.
- `store_binding` = lowercase hex `SHA-256` of the ASCII concatenation of that job's unique `store_name` values sorted lexicographically and joined by a single newline (no trailing newline if empty).
- Signed UTF-8 message: `domain + "\n" + job_id + "\n" + merkle_root + "\n" + manifest_sha256 + "\n" + store_binding`.
- `signature_hex` = lowercase hex of `HMAC-SHA256(mac_key, message)`.

## Ledger

`/app/output/ledger.json`: `{ "entries": [ ... ] }` for successful jobs in manifest order only.

Each entry keys: `job_id`, `merkle_root`, `store_binding`, `prev_hash`, `entry_hash`.

- First `prev_hash` = 64 zero hex digits.
- `entry_hash` = lowercase hex `SHA-256` of ASCII `prev_hash + job_id + merkle_root + store_binding` (no delimiters).

## Archive

`/app/output/jobs/<id>/archive.tar.gz` is gzip wrapping a ustar tar of every non-excluded path under the job `src`, in lexicographic path order.

- Symlinks: typeflag symlink, link name = target, size 0.
- Hardlink non-primaries: typeflag hardlink, link name = primary relative path, size 0.
- Regular and hardlink primaries: typeflag regular, size = logical byte length, content = full expanded bytes.
- Header fields: mode from `Lstat`, uid/gid 0, uname/gname empty, mtime 0, format ustar.
- Gzip level from config; use Go `gzip.Writer` with that level. No extra gzip headers beyond level defaults.

## JSON artifacts and key order

All JSON except `report.jsonl` lines: UTF-8, two-space indent, one trailing newline.

`/app/output/report.jsonl`: one compact JSON object per manifest job (no spaces), final newline after the last line. Keys in order: `job_id`, `status`, `file_count`, `byte_count`, `chunk_count`, `unique_chunks`, `merkle_root`. Failed/quarantined rows set metric fields to `null` and `merkle_root` to `null`.

Successful job directory `/app/output/jobs/<id>/`:

1. `manifest.json` — `{ "job_id", "files": [ ... ] }` where each file object keys are `path`, `kind`, `size`, `file_id`, `chunk_ids`, `link_target`, `primary_path`. For regular/primary: `link_target` and `primary_path` are `null`. For symlink: `chunk_ids` is `[]`, `file_id` is `null`, `link_target` is the target string. For hardlink alias: `chunk_ids` copies the primary, `file_id` equals primary, `primary_path` set, `link_target` null. Files sorted by `path` ascending.

2. `chunk_catalog.json` — `{ "chunks": [ { "chunk_id", "store_name", "size", "ref_count" } ] }` sorted by `chunk_id` ascending.

3. `dedup_report.json` — `{ "job_id", "total_files", "primary_files", "alias_files", "total_bytes", "stored_bytes" }` where `stored_bytes` sums sizes of chunks first written by this job into the store.

4. `restoration_map.json` — `{ "job_id", "entries": [ { "path", "kind", "file_id", "chunk_ids", "holes", "primary_path" } ] }` sorted by `path`. `holes` is a list of `{ "offset", "length" }` in ascending offset order (empty list when none).

5. `summary.json` — `{ "job_id", "file_count", "byte_count", "chunk_count", "unique_chunks", "merkle_root", "gzip_level" }`.

6. `archive.tar.gz`

7. `attestation.json` as specified above.

Also write `/app/output/global_chunk_registry.json`: `{ "chunks": [ { "chunk_id", "store_name", "size", "ref_count" } ] }` for every chunk across successful jobs, sorted by `chunk_id`.

## Batch outputs (required)

1. `/app/output/policy_receipt.json`
2. `/app/output/report.jsonl`
3. `/app/output/global_chunk_registry.json`
4. `/app/output/ledger.json`
5. `/app/output/chunk_store/`
6. Per successful job artifacts listed above

## Supplemental remote catalog

When `/app/resources/remote_catalog/extra_jobs.json` exists, it is a JSON array of objects `{ "id", "src", "config" }` with `src` and `config` paths relative to `/app/resources/remote_catalog/`. After processing every job in `/app/data/manifest.json`, process these supplemental jobs in array order using the same rules, continuing the shared chunk store and ledger chain. Re-derive policy material only once at the start of the run (still via the live pinned URL).
