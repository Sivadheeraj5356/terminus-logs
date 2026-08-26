# Write a Go program, compiled to /app/hmm, that replays and analyses the duration

Submission: `0efd21c1-4598-4c4b-8541-a981d5a3e1cd`  
Slug: `write-a-go-program-compiled-to-app-hmm-that-replays-and-anal`  
Latest archive: `0efd21c1-4598-4c4b-8541-a981d5a3e1cd_submission_2026-07-20T22_50_32.989Z.zip`  
Revisions: 1

## Task summary

Write a Go program, compiled to /app/hmm, that replays and analyses the duration-explicit recording process described by the cases in /app/data/cases.txt. Each case gives model parameters and a 64-bit seed but no recording. Your program has to produce three things per case, written one case at a time in input order to /app/output/results.txt at full double precision. First the exact recording the reference process emits for that seed, entry for entry. Then the log-likelihood of that recording under the model, treating the seed as unknown. Then the expected number of visits the window intersects given the recording. It should also take an input path and an output path as command-line arguments so it can run on other case files. With no arguments it uses those two defaults. Use only the Go standard library and do the work in the compiled binary, no shelling out to Python or anything else. The hard part is that the docs alone are not enough. /app/docs/hmm-spec.md pins the model family, the splitmix64 stream, the categorical scan rule, the visit-boundary draws, the whole recording layer, the schemas, the tolerances, and even how many draws the window opening consumes. What it deliberately does not document is the law behind that opening. The recording starts on a visit already in progress, and the distribution governing that visit's age and total length is left to discovery. The probe reference at /app/ref is the authority on it. It answers any case file in the same format at full precision but refuses anything longer than 128 steps, and the graded cases run to several...

Required artifacts include: `/app/hmm`, `/app/data/cases.txt`, `/app/output/results.txt`, `/app/docs/hmm-spec.md`, `/app/ref`.

Author anonymous tagged this **hard** machine-learning task (hmm, hidden-semi-markov, duration-modeling, smoothing, censoring, missing-data, probe-reference, black-box-identification, log-space, numerical-stability, probabilistic-models, machine-learning, go).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `0efd21c1-4598-4c4b-8541-a981d5a3e1cd_submission_2026-07-20T22_50_32.989Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
