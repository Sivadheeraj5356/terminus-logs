# Transit photometry desk operations

Entrypoints:

- `/app/scripts/build.sh` compiles `desk` and `legacy` into `/app/bin`.
- `/app/scripts/run_desk.sh` rebuilds and refreshes `/app/output/depth_report.json`
  plus `/app/output/matrix.transcript`.
- `/app/scripts/ref-depth` prints the uninterrupted depth product for each pack
  (sealed copy also lives under `/opt/verifier/ref-depth`).
- Fresh-lane totals come from the sealed `/opt/verifier/legacy` binary when present.

Work bundles land under `/app/work/<pack>.bundle`. Curve packs live under
`/app/curves`. Pack order is `/app/shared/pack_index.json`.

Report rows carry pack, fresh_depth, resumed_depth, second_depth,
residual_fresh, residual_resumed, depth_parity_ok, and dual_resume_ok. The
header uses schema_version; the summary reports all_parity_ok and pack_count.
