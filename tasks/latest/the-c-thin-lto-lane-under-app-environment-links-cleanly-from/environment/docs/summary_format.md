# Thin summary sidecar format

Each module writes `/app/work/lto/<module>.summary.json` after object emission.

Fields:

- `module` — logical module name (`anchor`, `dispatch`, `consumer`, `gate_abi`, `main`)
- `import_hash` — digest of import-resolution inputs for the module
- `abi_tag` — optional ABI stamp text associated with the module summary; when populated from `/app/work/gen/abi_stamp.txt`, store the trimmed text with leading and trailing whitespace removed
- `object_sha256` — digest of the emitted `.o` file
- `source_mtime` — timestamp of the primary source file used for the module build
- `link_epoch` — integer generation stamp recorded on import-sensitive sidecars

Sidecars live at `/app/work/lto/<module>.summary.json` (for example `/app/work/lto/dispatch.summary.json`).

Import-sensitive modules record the same trimmed `abi_tag` whenever `/app/work/gen/abi_stamp.txt` is present.

The epoch journal at `/app/work/lto/epoch_journal.json` holds `{"generation": <int>}`. After a cold full link the generation is 1. After a pass script completes, every import-sensitive sidecar must carry the same `link_epoch`, and that value must equal the journal `generation` when the journal file is present.

Checkpoint manifests at `/app/work/checkpoint/manifest.json` record `replay_seq`, `journal_generation`, `dispatch_seed`, and `abi_tag` from the profile at checkpoint time. After restore, incremental passes must reconcile a missing or lagging journal to `journal_generation` before evaluating relinks.

# Observation report schema

`/app/output/lto_observation.json` uses `report_version` 1 with `matrix` rows and an `incremental_transcript`. Each matrix row includes `scenario`, `profile`, per-module `summary_hash`, sorted `linked_symbol_set`, `binary_sha256`, and `probe` with integer `lane`, `seed`, and `mixed` plus string `abi_tag` from `/app/work/bin/matrix_app --probe`. Digests use SHA-256 (64 lowercase hexadecimal characters). Incremental link reports written via `--report` include `relinked_modules`. The ABI profile at `/app/environment/gen/abi_profile.json` carries `abi_tag` and integer `dispatch_seed` fields consumed by header generation.
