# # Feature Store Training Leakage and Model Deployment Gate

Submission: `fd6e06f4-5580-4ea5-9d04-8af9d848f5c0`  
Slug: `feature-store-training-leakage-and-model-deployment-gate`  
Latest archive: `fd6e06f4-5580-4ea5-9d04-8af9d848f5c0_submission_2026-07-20T22_14_59.402Z.zip`  
Revisions: 1

## Task summary

Certify each ML model training run stored in `/app/data/lineage.duckdb` before deployment: Repair `/app/src/feature_audit.c` so the training-compliance evaluator writes correct ML governance artifacts under `/app/output/`. Policy cutoffs, registry base URL, freshness column, violation detail templates, lineage digraph layout, and contract tokens are supplied by the live inputs under `/app/data/` (including `governance_policy.json`, the graph emission binding selected for this feature-store domain, and `contract_binding_requirements.json`). Key requirements: **Feature leakage** — reject training runs that bind features whose store availability timestamp is after the training ledger cutoff (temporal leakage into the training window).; **Model registry gate** — reject training runs whose model artifact fails the live model-deployment registry check.; **Feature lineage** — for rejected runs, emit a Graphviz feature-lineage diagram of the training feature graph..

Required artifacts include: `/app/data/lineage.duckdb`, `/app/src/feature_audit.c`, `/app/output/`, `/app/data/`, `/app/src`, `/app/bin/feature_lineage_verdict`, `/app/data/governance_policy.json`, `/app/output`.

Author anonymous tagged this **hard** machine-learning task (machine-learning, mlops, feature-store, feature-leakage, training-pipeline, model-deployment, model-governance, feature-lineage).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Harbor smoke runs are in `jobs/`. Oracle (`jobs/smoke-oracle`) scored **reward 1.0** in 1m 1s — the task is solvable and the verifier works. Two Terminus-2 attempts (`jobs/2026-08-23__04-09-18` and `jobs/smoke-openai-gpt4o`) never reached the verifier: both died in LiteLLM auth (`API key is invalid` / `Incorrect API key provided`). Those are infra errors, not valid fails, so they do not count as stumping.

## Agent summary

Terminus-2 started inside the container (`recording.cast` exists) and received the feature-store instruction, then the LLM call failed before any agent commands ran. No real attempt, plan, or wrong turn was recorded. `ANTHROPIC_API_KEY` on this machine is an OpenAI-style `sk-proj-...` key and is rejected by both Anthropic and OpenAI. A valid `sk-ant-...` or working `OPENAI_API_KEY` is required to produce a real agent summary. After that, run `scripts/run_agents.ps1` then `python scripts/update_catalog_from_jobs.py`.

## Stump the models?

- Oracle: 1/1 solved (not a stump signal)
- Terminus-2 / claude-sonnet-4-5: infra (invalid Anthropic key)
- Terminus-2 / gpt-4o: infra (invalid OpenAI key)
- Valid-fail stump %: unknown
- Band: `no_logs`
