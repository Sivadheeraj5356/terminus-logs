The feature-aware build coordinator under `/app/environment` must certify that every expanded task graph stays acyclic across flag combinations.

Primary arms in `/app/environment/docs/primary_flags.txt` look sound after `bash /app/environment/scripts/bp_run`, but held-out rows from `/app/environment/data/extra_flags.toml` show stuck counters or non-zero lag. Echo pairs disagree on facet material, witness sidecars under `/app/output/witness_meta/` disagree with the JSON certificate, and the status probe can read steady while the report is incoherent.

Repair the TypeScript implementation so a normal driver run regenerates `/app/output/cert_report.json`, traces under `/app/output/run_traces/`, witness bytes, and `/app/environment/state/k3_ledger.tsv`. Public schema, witness binding rules, and replay commands are in `/app/environment/docs/formal_rules.md`; argv hooks in `/app/environment/docs/operator_cmds.txt`.

The terminal report must satisfy the row_v4 contract in formal_rules: coherent terminal rows, matching echo pairs, `summary.sync_label` and `cert_digest` as defined there, and generalization across every scenario in extra_flags.toml. Witness sidecars under `/app/output/witness_meta/` must biject with coherent non-echo base rows only; echo rows (`*_echo`) stay in the report but must not write their own `.bin` files. Perturbing `floor` in `/app/environment/data/flag_lattice.toml` must change facet material and `cert_digest`.

Each row's `expand_rc`, `merge_rc`, and `proof_rc` values must come from the wired mux helper return codes on the phase path in formal_rules, not from recomputed success predicates in orchestration wrappers. Helper fault propagation is part of the contract: when a mux helper returns incomplete or failed results, the matching counter must reflect that fault instead of being forced to success by defensive pipeline logic.

Rebuild with `make -C /app/environment bp_run` after edits. Hand-written or static output is insufficient; the normal driver pipeline must regenerate every artifact. Wrapper-only validation, hardcoding row counters in orchestration code, or skipping the driver pipeline will not pass.
