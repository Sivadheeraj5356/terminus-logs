# OV publication contract

## Suite modes

```bash
bash /app/environment/scripts/build_workspace.sh
/app/environment/tools/ov_probe/ov_probe --suite all --trace-out /app/output/ov_trace.json
/app/environment/tools/ov_probe/ov_probe --suite rebuild
/app/environment/tools/ov_probe/ov_probe --suite prop
/app/environment/tools/ov_probe/ov_probe --suite prepare
/app/environment/tools/ov_probe/ov_probe --suite finalize --trace-out /app/output/ov_trace.json
bash /app/environment/migrations/rst9.sh --repair
```

`--suite all` grades every case in `/app/environment/cases/idx.json` on both arms (`arm_a`, `arm_b`). `--suite rebuild` deletes any prior graded trace, re-runs from live sources, and must agree with a fresh full suite at the same cycle. `--suite prop` may write `/app/output/smoke_trace.json` with `PARTIAL_OK` without proving graded coherence. `--suite prepare` performs arming hygiene and writes `arm_token` without grading rows or bumping `suite_gen`. `--suite finalize` grades rows and consumes the token without a fresh prepare (fails if the token is missing or does not match the live-bound nonce). Digests are sha256; verifiers may check them with `openssl dgst -sha256` over the canonical row bytes.

## Trace schema

`/app/output/ov_trace.json` is a JSON array. Each object:

| Field | Type | Rule |
|-------|------|------|
| `unit_id` | string | Case unit id |
| `arm` | string | `arm_a` or `arm_b` |
| `sel_id` | string | `slotA` or `def` |
| `fetch_seq` | int array | Workspace slot integers after first-wins dedupe |
| `scheme` | string | Joint authority scheme (`prv`, `file`, or `eng`) |
| `uri_scheme` | string | URI-prefix-only map (`prv`/`file`/`eng`) ignoring selection |
| `digest` | string | 64 lowercase hex characters |
| `status` | string | Graded rows must be `WIT_FRESH` (see `evt_lex.md`) |

## Definitions

- `weight` = count of `slot=` lines in `/app/environment/conf/workspace.conf` (duplicates count).
- `epoch` = (sum of slot integers, duplicates counted) XOR mask from `/app/environment/var/mig/epoch_mask.json`.
- `auth_gen` = integer from `/app/output/.ov_persist/bind_stamp.json` field `auth_gen` if the file exists, else `0`.
- `cycle` = integer in `/app/environment/var/mig/suite_gen` if present else `0` (read at prepare; finalize increments by one after successful consume).

## Selection

If the case `query` contains `strict` and `/app/environment/conf/<arm>.conf` contains `slot=A`, then `sel_id` is `slotA`. Otherwise `sel_id` is `def`. Preference latch must not remap selection. Prepare must clear latch to absent or empty before selection runs.

## Fetch sequence (first-wins)

`fetch_seq` is built from `slot=` lines in `/app/environment/conf/workspace.conf` in file order. When the same integer appears more than once, keep only the first occurrence and skip later duplicates. Live edits to that file are authoritative.

## Scheme ternary (joint) vs URI-only

`uri_scheme` maps the case URI alone: `prv:` → `prv`, `file:` → `file`, otherwise `eng`.

`scheme` (joint authority) depends on both URI and `sel_id`:

- When `sel_id` is `slotA` and the URI begins with `file:`, `scheme` must be `file` (URI wins).
- When `sel_id` is `slotA` otherwise, `scheme` must be `prv`.
- When `sel_id` is `def`, `scheme` equals `uri_scheme`.

On coherent `slotA` rows with non-`file:` URIs, `scheme` and `uri_scheme` therefore disagree (`prv` vs URI map).

## Digest (eight segments)

`digest` is sha256 of the eight-segment canonical row (no trailing newline), printed as 64 lowercase hex characters drawn from the alphabet `0123456789abcdef`:

```
<unit_id>|<arm>|<sel_id>|<fetch_seq comma-joined>|<scheme>|<epoch>|<cycle>|<weight>
```

`<epoch>` is the decimal string of the live expected epoch.
`<cycle>` is the decimal string of the suite generation counter read at prepare time.
`<weight>` is the decimal string of the live slot-line count.

If `rim_residue` is non-empty at digest time, its content is appended as an extra `|` segment and digests diverge from the eight-segment formula. Coherent suites leave residue empty before hashing.

## Persist surfaces (`/app/output/.ov_persist/`)

- `rim_residue` — must be empty during hashing on a coherent suite
- `mig.jnl` — one 16-hex digest prefix per graded row; truncated at prepare
- `pref_latch` — after a successful finalize / full graded suite, the file must exist and contain exactly `sealed` (no suffix). Prepare must leave the file empty or absent. A non-empty latch file counts as active for selection checks.
- `arm_token` — one-shot arming nonce
- `bind_stamp.json` — `{"auth_gen": N, "epoch": E}` written at finalize

### Arming budget

Token bytes are the first 16 lowercase hex characters of sha256 over:

```
epoch_decimal + "|" + idx_bytes + "|" + mask_bytes + "|" + weight_decimal + "|" + auth_gen_decimal
```

using the live expected epoch string, the live bytes of `/app/environment/cases/idx.json`, `/app/environment/var/mig/epoch_mask.json`, live weight, and live `auth_gen` from `bind_stamp.json` (or `0` only when that file is absent). Prepare and finalize must not substitute `suite_gen` or a constant zero for `auth_gen` when `bind_stamp.json` is present. Finalize recomputes the nonce from the live binders at consume time, so mutating `bind_stamp.json` between prepare and finalize must fail consume.

- Prepare fails if `arm_token` already exists (including opaque leftovers).
- Prepare creates the token with the live-bound nonce; does not bump `suite_gen`.
- Finalize recomputes the nonce, consumes/deletes the token (fails if missing or mismatch), sets `pref_latch` content `sealed`, writes `bind_stamp.json` with `auth_gen` equal to the post-increment `suite_gen` and `epoch` equal to the expected epoch, and increments `suite_gen` by one. Finalize must not copy `mig.jnl` into `rim_residue`.

### Preference latch vs odd epoch

Under an odd epoch, a sticky non-empty latch must not force strict `arm_a` rows from `slotA` to `def`, and must not remap joint scheme away from the ternary rule.

## Epoch and seal stamp

Expected epoch = `(sum of all workspace slot integers, counting duplicates) XOR (mask from epoch_mask.json)`.

If `/app/environment/var/mig/seal_stamp.json` exists and its `epoch` field disagrees with the expected value, prepare clears residue, journal, and latch but must not rewrite the stamp file. Stamp agreement must not skip those clears: matching stamps still require a full prepare hygiene pass.

## Recovery wipe

`rst9.sh --repair` clears `/app/output` (including the graded trace and persist dir) and removes `suite_gen`. After repair, `/app/output/ov_trace.json` and `suite_gen` are absent until the next successful graded cycle.

## Decoys

Helpers under `q8/`, `r4/`, and `t6/` that print green-looking lines are not graded. Property-only smoke output does not waive a failing graded suite.

Stock regression snapshots under `/app/environment/share/ref_blobs/` hold alternate ord/bind module bodies (files `ord.go` and `bind.go`) used only when the verifier temporarily swaps live sources for ablation runs. Those two baseline files must remain unmodified for the whole graded run; verifiers compare them against protected copies and hashes under `/opt/verifier/` before and after grading. Verifiers may restore those blobs onto `/app/environment/r4/ord.go` and `/app/environment/t6/bind.go`; after such a swap, first-wins `fetch_seq` or `slotA` scheme outcomes must regress to the stock broken behavior. Authority for those outcomes must therefore live in those publication modules, not only in `ov_probe` wrappers. Opaque planted residue string `poison-residue-hex` must be cleared before coherent hashing.
