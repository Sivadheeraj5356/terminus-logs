# cross-surface contract (k4)

These rules bind `/app/output/staging_manifest.json`, `/app/output/phase_journal.json`, and `/app/output/loader_trace.json` to the live staging sidecars under `/app/.staging/`. Local mirrors live under `environment/tools/`.

## driver entry

Regenerate outputs with `bash /app/environment/driver/exec_w0.sh --profile warm`, `bash /app/environment/driver/exec_w0.sh --profile cold`, `bash /app/environment/driver/exec_w0.sh --profile cold --merge`, and `bash /app/environment/driver/exec_w0.sh --profile cold --merge-tier 2`.

## profiles and weights

Profile labels, required object sets, and weight table paths are in `environment/data/profiles.json`. Weight tables under `environment/bundles/profiles/` assign integer weights per object. Sort by descending weight, then ascending object name. Equal-weight pairs such as `mod_net` and `mod_rtc` on the cold table must follow name order in `read_order` and in both index views.

## stamp and carry

`stamp` is the first 16 hex digits of sha256 over a body that joins `profile`, semicolon-joined sorted object names, and `carry_token` with `:` separators (`profile:names:carry_token`). Host bind must compute that digest through the shared helpers under `environment/lib/` so stamp body layout stays identical for epoch ledger tooling and journal lane ranking. Name lists inside the stamp body use ASCII semicolon separators only; weight ranking helpers must sort by descending weight then ascending name, not by bare name order.

`carry_token` on each driver run must reflect the active wave snapshot at `/app/.staging/active_wave.json`, not a cached value from an earlier run. When the driver profile or merge tier changes within a session, any carry sidecar cache under `/app/.staging/` must be discarded before carry resolution runs. Wave staging must rebuild `/app/.staging/active_wave.json` on every driver invocation, including when only `--merge` or `--merge-tier` changes while the `--profile` label stays the same. Wave bundles under `environment/bundles/waves/` define parent and delta object sets; incremental `--merge` folds `wave_b.json` onto the parent snapshot and adopts carry label `WAVE_B`, and `--merge-tier 2` folds `wave_c.json` onto the tier-1 snapshot and adopts carry label `WAVE_C`. Plain cold runs keep parent carry label `WAVE_A`. Tier-1 merged active waves contain 6 objects; tier-2 merged active waves contain 7 objects; plain cold active waves contain 5 parent-wave objects.

## staging_manifest

`staging_manifest.json` records `profile`, `stamp`, `carry`, and staged `objects`. `profile` must match the `--profile` argument. `objects` must match the active wave snapshot for the selected merge tier. Within `objects`, rows follow the active profile weight table: descending weight, then ascending object name (same ordering as `read_order` restricted to staged names). `mod_disk` must stage only after tier-1 merge from `wave_b.json`; `mod_sensor` must stage only after tier-2 merge from `wave_c.json`. `fw_alpha` must stage on blob-lane B; `fw_beta` must stage on blob-lane B; `mod_core` must stage on object-lane O.

## phase_journal

The `phase_journal` stream reports a `segments` array. Each segment must record `lane` (`B` or `O`), `epoch`, `blob_epoch`, `hook_gen`, and staged object names. Blob-lane segments precede object-lane segments. Within each segment, object names follow the active profile weight table: descending weight, then ascending name. `hook_gen` advances once per emitted segment and must stay strictly increasing. `blob_epoch` advances when blob-lane staging completes and is inherited unchanged on object-lane rows. The union of staged object names across segments must equal the active wave object set.

## hook gate

`/app/.staging/hook_state.json` carries one `commits` row per journal segment (`lane`, `hook_epoch`, `committed`). A row is committed (`committed` true) only when that segment's `blob_epoch` equals `hook_gen`; otherwise `committed` is false. The driver must schedule hooks with `hook_epoch` 1. Object-lane availability in the loader may inherit a successful blob-lane commit, but the hook_state row for object-lane still records `committed` false until the counters match.

## loader_trace

`loader_trace.json` reports `profile`, `read_order`, `rows`, and `status_token`. `profile` must match `staging_manifest.json` `profile` on every driver run. `read_order` lists every weight-table object for the profile using the weight sort above, not manifest insertion order or raw name sort. The `rows` array must follow `read_order` sequence: `rows[i].object` equals `read_order[i]` for every index. Emit one schema-valid row per weight-table object (`environment/schemas/trace_row.schema.json`). Each row `avail_metric` is 1 only for required objects that are present in both the staging manifest and the phase journal object union and that pass hook gating; object-lane rows may inherit a successful blob-lane hook commit on every profile, not only warm. Otherwise `avail_metric` is 0. `status_token` is `CLEAN` only when every required object for the profile has `avail_metric` 1, else `DIRTY`, even if driver stderr prints a clean status line.

## index parity

`host_index.json` and `chroot_index.json` must expose identical `order` arrays containing only active-wave object names sorted by profile weights. Index lists must not include weight-table objects absent from the active wave. Plain cold index lists contain 5 names; tier-1 merge lists contain 6 names; tier-2 merge lists contain 7 names. `worker_hint.json` mode must keep host and chroot views on weight ordering for both warm and cold profiles rather than name-sorted fallbacks on either profile. `probe_order.json` from the host depmod probe must not override index binding or force name-sorted chroot fallbacks.

## epoch ledger

`/app/.staging/epoch_ledger.json` tracks `rev` and `last_stamp`. After each driver run, `last_stamp` must equal the manifest `stamp`. `rev` increments by exactly 1 when the manifest stamp changes between runs in the same session; identical consecutive runs with the same stamp must leave `rev` unchanged.

## glossary

See `environment/data/glossary_tokens.json` for `BLOB_EPOCH`, `HOOK_GEN`, `CLEAN`, and carry token labels.
