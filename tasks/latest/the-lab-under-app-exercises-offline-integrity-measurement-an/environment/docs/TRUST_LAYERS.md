# Split trust layers

The lab models tiered file-read integrity measurement and appraisal. No single
component owns the full enforcement story.

## Authority pin

The loader does not open `data/policy.json` directly. It reads
`data/authority/pin.json`, `data/authority/index.json`, and
`data/authority/stamp.json`. The pin names an index lane (`live`, `hold`, or
`arm`). The stamp seeds define a covenant epoch `a*3 + b*2 + c`. When the pin
epoch does not match that covenant, the loader falls back to the `live` lane.
The `arm` lane points at the production policy bundle; other lanes point at
staged overlays that are not the production contract.

## Lowering pass (Go loader)

Resolves the authority pin, materializes bind roots into `output/program.json`,
and emits the flat job list. Bind resolution here determines which roots the
replay worker and reconcile pass treat as authoritative.

## Replay worker (Rust hook)

Replays workload reads against the lowered program, records verb dispatch in
`output/read_traces.json`, and writes digest rows to `output/measure_log.json`.
Coverage, band selection, and digest row keys must agree with the model.

## Reconcile roll-up (Go audit)

Compares traces, the digest log, and `data/manifest.json` into
`output/integrity_report.json`. It re-derives the winning band and active verbs
per read from the lowered program, folds appraisal against manifest fields, and
sets `aligned`. Trace verb lists are observational; they are not a substitute
for re-deriving enforcement from the program.

Reconciling a single layer alone leaves other workload scenarios misaligned
when authorities still disagree. See `POLICY_ROLLOUT.md` and
`ATTESTATION_CHAIN.md`.
