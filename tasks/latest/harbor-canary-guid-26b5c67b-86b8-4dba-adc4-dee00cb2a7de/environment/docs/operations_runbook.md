# Batch Reconciliation Runbook

The evening batch is prepared under `/app/in`, reconciled by
`/app/bin/reconcile_ink`, and written to `/app/out/ink_report.csv`.
Operations treats `/app/docs/unity_denomination_spec.md` as the policy source
for denomination weights and `/app/config/reconcile.toml` as the runtime
module binding.

When audit failures appear, compare the live report, the audit-failure log,
and the denomination spec before changing the input feed. For estimator
repairs, spec §6.2 documents the two-phase carry DP bounds (canonical bound,
optional small-window probe, then full cost-bounded search) that upper-range
regression inputs require. The settlement CSV is a regulated batch artifact
and must remain byte-stable during repair.
