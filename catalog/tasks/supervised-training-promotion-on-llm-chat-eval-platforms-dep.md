# Supervised training promotion on LLM chat-eval platforms depends on contaminatio

Submission: `32790a15-9742-4b9f-a33e-b553d9650d7e`  
Slug: `supervised-training-promotion-on-llm-chat-eval-platforms-dep`  
Latest archive: `32790a15-9742-4b9f-a33e-b553d9650d7e_submission_2026-07-18T20_26_37.982Z.zip`  
Revisions in Dropbox: 2

## Task summary

Supervised training promotion on LLM chat-eval platforms depends on contamination-aware inference features before failed assistant turns are admitted as clean supervision for the next fine-tune cut. Stale retrieval hashes, conflicting system-instruction versions, tool-artifact bleed, and repeated fact injections each leave different fingerprints on the turn timeline and distort training-signal eval metrics and inference feature batches. Build the wincontam training-signal evaluator under /app as an ML eval capability that attributes contaminated failures from conversation manifests, scores per-session severity metrics, and seals a freeze-bound risk bulletin so later emission cannot silently rescore a mutated tree used as training features:

Required artifacts include: `/app/data`, `/app/docs/ml-training-signal-contamination.md`, `/app/docs/feature-eval-metric-contract.md`, `/app/docs/contam-eval-workflow.md`, `/app/docs/contam-attribution.md`, `/app/docs/risk-bulletin-schema.md`, `/app/docs/context-hold-freeze.md`, `/app/docs/mutation-chain-receipt.md`.

Author anonymous tagged this **hard** machine-learning task (nlp, llm, feature-pipeline, eval-metrics, training-signal, inference-features, contamination-attribution).

Time estimates: expert ~360 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `32790a15-9742-4b9f-a33e-b553d9650d7e_submission_2026-07-18T20_26_37.982Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
