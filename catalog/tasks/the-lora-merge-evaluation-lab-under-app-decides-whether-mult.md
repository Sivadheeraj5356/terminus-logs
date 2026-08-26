# The LoRA merge evaluation lab under /app decides whether multi-adapter PEFT cand

Submission: `7fcabcea-a975-4c20-8a9f-bdd23dadd8aa`  
Slug: `the-lora-merge-evaluation-lab-under-app-decides-whether-mult`  
Latest archive: `7fcabcea-a975-4c20-8a9f-bdd23dadd8aa_submission_2026-07-19T16_57_24.778Z.zip`  
Revisions in Dropbox: 2

## Task summary

The LoRA merge evaluation lab under /app decides whether multi-adapter PEFT candidates are safe to launch on a pinned base checkpoint. Score each launch candidate with /app/lora-gate <request-file> and publish the model-readiness board at /app/output/lora_merge_conflict_gate.json plus per-adapter findings at /app/output/adapter_findings.jsonl. Requests use the existing line-oriented adapter/manifest interface documented by the source parser, including base checkpoint, revision, held-out evaluation parts, merge-risk limit, alias lines, and adapter leaf rows. The readiness board is a JSON object where request_id and model_view are strings, ready is boolean, score is an integer, and targets is an array of strings. Findings are JSONL rows where request_id, model_view, and adapter are strings, ready is boolean, and score is an integer. Target module lists are sorted and deduplicated; finding lines follow adapter input order. Both artifacts must agree on request identity, composed model view, launch readiness, and merge-risk score.

Required artifacts include: `/app/lora-gate`, `/app/output/lora_merge_conflict_gate.json`, `/app/output/adapter_findings.jsonl`.

Author anonymous tagged this **hard** machine-learning task (lora, peft, adapter-merge, checkpoint-eval, launch-readiness).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7fcabcea-a975-4c20-8a9f-bdd23dadd8aa_submission_2026-07-19T16_57_24.778Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
