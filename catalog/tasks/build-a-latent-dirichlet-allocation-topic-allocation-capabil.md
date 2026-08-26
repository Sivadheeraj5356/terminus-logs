# Build a Latent Dirichlet Allocation topic-allocation capability under /app on th

Submission: `a2065d0a-7c9d-46db-b8ad-7d363f047d25`  
Slug: `build-a-latent-dirichlet-allocation-topic-allocation-capabil`  
Latest archive: `a2065d0a-7c9d-46db-b8ad-7d363f047d25_submission_2026-07-21T02_10_16.490Z.zip`  
Revisions in Dropbox: 2

## Task summary

Build a Latent Dirichlet Allocation topic-allocation capability under /app on the supplied working Rust workspace. Implement patent document ingest, corpus staging, a deterministic collapsed-Gibbs sampler, a posterior count ledger, and a sealed topic rollup export according to /app/docs/cli.md, /app/docs/document-format.md, /app/docs/vocabulary.md, /app/docs/initialization.md, /app/docs/conditional.md, /app/docs/count-ledger.md, /app/docs/burn-in.md, /app/docs/topic-ranking.md, /app/docs/rollup-export.md, /app/docs/decoy-tfidf.md, and /app/docs/crate-modules.md. ldactl ingest reads JSON patent documents from the configured inbox and writes /app/state/lda-corpus-staging.json. ldactl sample reads only that corpus snapshot, runs the collapsed-Gibbs sampler, and writes /app/state/lda-count-staging.json. ldactl export reads only the two state snapshots and writes /app/output/lda-topic-rollup.json. ldactl status reports from state and never reads the output. Preserve deterministic ordering and byte identity on unchanged reruns.

Required artifacts include: `/app/docs/cli.md`, `/app/docs/document-format.md`, `/app/docs/vocabulary.md`, `/app/docs/initialization.md`, `/app/docs/conditional.md`, `/app/docs/count-ledger.md`, `/app/docs/burn-in.md`, `/app/docs/topic-ranking.md`.

Author anonymous tagged this **hard** machine-learning task (lda, topic-model, collapsed-gibbs, posterior, corpus, rollup).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `a2065d0a-7c9d-46db-b8ad-7d363f047d25_submission_2026-07-21T02_10_16.490Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
