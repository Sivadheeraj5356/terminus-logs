# # Repair the consolidated multi-entity three-statement model

Submission: `009e26d2-760a-43f7-8d97-903caf8d35b2`  
Slug: `repair-the-consolidated-multi-entity-three-statement-model`  
Latest archive: `009e26d2-760a-43f7-8d97-903caf8d35b2_submission_2026-07-07T14_54_38.509Z.zip`  
Revisions in Dropbox: 1

## Task summary

The Go program in `/app/main.go` reads a manifest JSON path from `os.Args[1]`, joins the three documents it references (`group`, `entities`, `intercompany`), projects the three financial statements for every entity in the group, computes coverage covenants, and consolidates the group. The model is mostly built but does not tie out. Fix the model code only, keeping the same command-line interface and the existing JSON documents, sections, and field names. The accounting rules the model must follow — how the documents join by entity id and period, the integer arithmetic conventions, the per-entity income-statement, tax, working-capital, equity, and circular debt/interest logic, the coverage covenants, and the consolidation with intercompany eliminations and minority interest — are documented in `/app/MODEL_SPEC.md`. A runnable example group is in `/app/example/` (`main.go /app/example/manifest.json`). Your repair is correct when every per-entity reconciliation check and every consolidated check is exactly zero and `final_checks.all_entities_balance`, `final_checks.consolidation_balances_all_years`, and `final_checks.circular_converged_all_years` are all true.

Required artifacts include: `/app/main.go`, `/app/MODEL_SPEC.md`, `/app/example/`, `/app/example/manifest.json`.

Author anonymous tagged this **hard** data-processing task (finance, financial-modeling, integer-arithmetic, circular-reference, working-capital, gaap, deferred-taxes, stock-based-compensation, multi-document, consolidation, minority-interest, intercompany-elimination, debt-covenants, multi-period).

Time estimates: expert ~420 min, junior ~960 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `009e26d2-760a-43f7-8d97-903caf8d35b2_submission_2026-07-07T14_54_38.509Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
