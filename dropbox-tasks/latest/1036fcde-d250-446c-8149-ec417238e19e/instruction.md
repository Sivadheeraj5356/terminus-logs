Journal vacuum oneshot ledger skew

After journal vacuum maintenance on this host, the shard-export oneshot unit (`verify-journal-export.service`) loses byte-ledger parity between `StandardOutput=journal` and `StandardOutput=file` launch settings. `journalctl -u verify-journal-export` shows truncated progress lines and collector-socket write abort when journald recycles mid-burst; the file-backed unit profile completes quietly on the same fixture packs.

Bring emit-side behavior under `/app/environment` into compliance with `/app/environment/docs/journal_contract.md` so the oneshot driver regenerates audited artifacts through the normal fixture sweep. Hand-written JSON under `/app/output`, unit-wrapper-only edits, or output-only rewrites are insufficient; grading rebuilds `/app/bin/verify-journal-runs` from edited sources and reruns the bundled packs.

Several stages remain incomplete before emit. Journal-wrapped stdout must stage bytes with probe-close after collector recycle, discard probe pending when a later slice in the same burst commits to observed, keep per-slice `pending`/`observed` checkpoints accurate, and flush trailing probe pending only at burst end. Collector recycle checkpoints must move pending into observed before epoch advance without zeroing observed totals. Slice planning must follow overlay-wins policy merge from bundled config. Resume offset and segment-cache sidecars apply only when fixture label and reader epoch both match the active seed. The delayed audit pass must reread report, journal, and manifest from disk and emit cross-artifact seals that agree with the live ledger. The `pack_m5` worked ledger table in the journal contract is authoritative for multi-recycle checkpoint sequences.

The oneshot must write `/app/output/run_records.json`, `/app/output/export_trace.jsonl`, `/app/output/span_journal.jsonl`, `/app/output/completion_manifest.jsonl`, `/app/output/run_audit.jsonl`, and `/app/output/run_ledger.state`. Schema bindings, digest formulas, fixture-pack discovery, and emit invocation live in `/app/environment/docs/journal_contract.md`.

`export_trace.jsonl` rows must include `fixture_label`, `phase`, `observed`, `pending`, `writer_epoch`, `reader_epoch`, and `span_mix`.
`span_journal.jsonl` rows must include `seq`, `fixture_label`, `phase`, `observed`, `pending`, and `link`.
`completion_manifest.jsonl` rows must include `fixture_label`, `journal_tail`, `trace_lines`, `wave_chunks`, and `completion_seal`.
`run_records.json` must include a `runs` array; each row includes `fixture_label`, `writer_epoch`, `reader_epoch`, `byte_span`, `fingerprint`, and `checkpoint_seal`.
`run_audit.jsonl` rows must include `fixture_label`, `journal_tail`, `completion_seal`, `checkpoint_seal`, and `audit_seal`.
`run_ledger.state` must include `run_count`, `prev_audit_tail`, and `chain_seal`.

Fixture packs live under `/app/environment/pack` with stems matching `pack_m*`. Bundled packs are `pack_m1` through `pack_m6` and `pack_m8`; `pack_m7` is not shipped and may appear only when added at runtime. Any `pack_m*.json` present before a run is discovered and included in all outputs on the same terms.
