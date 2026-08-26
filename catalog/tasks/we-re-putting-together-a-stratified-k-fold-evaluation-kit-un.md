# We're putting together a stratified k-fold evaluation kit under `/app` so a labe

Submission: `5bd7c1a8-74f0-448f-b30f-f088169b9fe8`  
Slug: `we-re-putting-together-a-stratified-k-fold-evaluation-kit-un`  
Latest archive: `5bd7c1a8-74f0-448f-b30f-f088169b9fe8_submission_2026-07-15T11_10_27.388Z.zip`  
Revisions in Dropbox: 14

## Task summary

We're putting together a stratified k-fold evaluation kit under `/app` so a labeled cohort CSV becomes deterministic fold IDs plus stratification diagnostics that a later CV or training loop can trust without redoing the split. The kit assigns folds and measures label balance; it does not train or score a model. Field shapes, digests, and seals are defined in `/app/schema/fold_manifest.schema.json` and `/app/schema/fold-digest-contracts.md`. Build with `mvn -q -f /app/pom.xml package`, then run `/app/bin/foldctl assemble --dataset PATH --folds K --label COLUMN` (that wrapper must exec the shaded jar under `/app/target` with Java). Keep `/app/pom.xml` packaging the `fold-assembler` shaded jar with main class `com.foldlab.FoldLabApp`. Staging goes through `/app/scripts/stage_cohort.sh`: it checks that the header has `id` and the chosen label column, copies the file bytes as-is to `/app/var/fold_work/cohort_staged.csv`, and exits non-zero if a required column is missing. Assemble must invoke that script via `bash`/`sh` with the script path as the first script argument (or exec the script path directly), then after writing the fold records call `Rscript /app/r/fold_balance.R /app/var/fold_manifest.json` with a real absolute `Rscript` executable and `/app/r/fold_balance.R` as argv[1]. R script interface: `/app/r/fold_balance.R` takes one argument (the manifest path), must print exactly one JSON object to process stdout and nothing else on stdout, must not create or edit that manifest path (or any other path) as a side effect, and exits 0 on success. The JSON object carries...

Required artifacts include: `/app/schema/fold_manifest.schema.json`, `/app/schema/fold-digest-contracts.md`, `/app/pom.xml`, `/app/bin/foldctl`, `/app/target`, `/app/scripts/stage_cohort.sh`, `/app/var/fold_work/cohort_staged.csv`, `/app/r/fold_balance.R`.

Author anonymous tagged this **hard** machine-learning task (stratified-cv, cross-validation, fold-assignment, balance-metrics, evaluation-kit, digest-chain).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5bd7c1a8-74f0-448f-b30f-f088169b9fe8_submission_2026-07-15T11_10_27.388Z.zip` is a task submission, not a Harbor job. 14 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
