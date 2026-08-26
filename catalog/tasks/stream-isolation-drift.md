# # Stream Isolation Drift

Submission: `59d3bc9c-831c-46e5-b51d-21201678874b`  
Slug: `stream-isolation-drift`  
Latest archive: `59d3bc9c-831c-46e5-b51d-21201678874b_submission_2026-07-12T12_08_59.068Z.zip`  
Revisions in Dropbox: 2

## Task summary

The derivative runtime under /app/environment emits JSONL run records and per-pass JSON summaries under /app/output. Serial runs look consistent. Under concurrent admission with checkpoint continue, norm summaries often stay within plan tolerance while pass files disagree with a serial baseline for the same plan, seed, and mode. Fix the source under /app/environment so the pipeline regenerates correct evidence. Output-only work is not allowed. Do not edit /tests/ or fabricate output files. Static or manual output creation is insufficient; the verifier deletes /app/output before each scenario and the normal run/continue pipeline must regenerate artifacts. Build, CLI flags, plan choices, and artifact schemas are in /app/environment/docs/contract.md; invoke the release binary through the run/continue pipeline described there. For a fixed plan, seed, and mode, sorted pass-record digest chains must agree between a serial uninterrupted run and a concurrent run that checkpoints mid-training and continues. Pass-record `mode` is stored for each pass but is not part of the digest formula. Successful runs emit `/app/output/run_transcript.jsonl` (seq, job, phase, slot, payload_digest, pass_index), per-pass JSON under `/app/output/pass_records/` (stream_fingerprint, open_slots, mode), and `/app/output/vault/manifest.json` (last_generation, last_pass, open_count). Digest formulas and CLI details are in the contract.

Required artifacts include: `/app/environment`, `/app/output`, `/app/environment/docs/contract.md`, `/app/output/run_transcript.jsonl`, `/app/output/pass_records/`, `/app/output/vault/manifest.json`.

Author anonymous tagged this **hard** scientific-computing task (rust, scientific-computing, autodiff, checkpoint, concurrency, reproducibility).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `59d3bc9c-831c-46e5-b51d-21201678874b_submission_2026-07-12T12_08_59.068Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
