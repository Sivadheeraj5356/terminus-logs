# Implement a single-pass, bounded-memory online classifier in Java. The stream co

Submission: `22c1b159-31d8-4557-b337-ef0d92e7af23`  
Slug: `implement-a-single-pass-bounded-memory-online-classifier-in-`  
Latest archive: `22c1b159-31d8-4557-b337-ef0d92e7af23_submission_2026-07-17T15_50_30.235Z.zip`  
Revisions in Dropbox: 1

## Task summary

Implement a single-pass, bounded-memory online classifier in Java. The stream contains one-minute household power rows with missing measurement gaps and delayed sub-meter labels. For each prediction request, your program must emit the probability that the source row's withheld sub-meter share crosses the request threshold, using only state available before any labels released at that same event. Your implementation lives in /app/environment/src/Solver.java and must build offline with javac. The file currently present there is only a placeholder stub that emits an empty result; replace it with a complete implementation. The verifier compiles it and runs java -cp /app/environment/src Solver <data-dir> once per stream. The program must print exactly one JSON document to standard output.

Required artifacts include: `/app/environment/src/Solver.java`, `/app/environment/src`, `/app/environment/docs/contract.md`.

Author anonymous tagged this **unknown** machine-learning task (streaming-ml, online-classification, delayed-labels, bounded-memory, concept-drift).

Time estimates: expert ~420 min, junior ~720 min.

Harbor timeouts: agent 1200s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `22c1b159-31d8-4557-b337-ef0d92e7af23_submission_2026-07-17T15_50_30.235Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
