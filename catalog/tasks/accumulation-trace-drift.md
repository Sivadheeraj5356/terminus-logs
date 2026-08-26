# # Accumulation Trace Drift

Submission: `ed3ed486-f775-46c4-b0d1-3b12f00ce93c`  
Slug: `accumulation-trace-drift`  
Latest archive: `ed3ed486-f775-46c4-b0d1-3b12f00ce93c_submission_2026-07-06T14_19_08.997Z.zip`  
Revisions in Dropbox: 1

## Task summary

The training runtime under /app/environment emits JSONL run records and per-pass JSON summaries under /app/output. Serial runs look consistent. Under concurrent admission with snapshot/continue — including partial-window halts mid accum window — norm summaries often stay within plan tolerance while pass files disagree with a serial baseline for the same plan, seed, and accum window. Fix the Rust sources under /app/environment so the pipeline regenerates correct evidence. Output-only work is not allowed. Do not edit /tests/ or fabricate output files. Static or manual output creation is insufficient; the verifier deletes /app/output before each scenario and the normal train/continue pipeline must regenerate artifacts. Build, CLI flags, plan choices, and fingerprint formulas are in /app/environment/docs/contract.md and /app/environment/docs/toolchain.md; invoke the release binary through the train/continue pipeline described there. For a fixed plan, seed, accum window, and mode, sorted pass step fingerprints must agree between a serial uninterrupted run and a concurrent run that snapshots mid-training and continues. The same serial baseline must also match for per-step accumulator checksum chains and for the sorted tag membership recorded at each completed step in the trace. Successful runs emit artifact families with distinct schemas: /app/output/run_trace.jsonl records seq, slot, phase, tag, payload_fp, and step_index on each line; /app/output/pass_transcripts/pass_<n>.json carries step_digest, balance_tally, pending_slots, mode, and acc_checksum for each completed step;...

Required artifacts include: `/app/environment`, `/app/output`, `/app/environment/docs/contract.md`, `/app/environment/docs/toolchain.md`, `/app/output/run_trace.jsonl`, `/app/output/pass_transcripts/pass_`, `/app/output/vault/manifest.json`, `/app/output/vault/acc.bin`.

Author anonymous tagged this **hard** scientific-computing task (rust, accumulation, snapshot, checkpoint, training-runtime).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `ed3ed486-f775-46c4-b0d1-3b12f00ce93c_submission_2026-07-06T14_19_08.997Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
