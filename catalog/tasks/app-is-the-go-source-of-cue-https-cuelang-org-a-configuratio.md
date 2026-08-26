# `/app` is the Go source of [CUE](https://cuelang.org), a configuration and

Submission: `a5a8dc20-9355-4f80-9929-23b01e704bff`  
Slug: `app-is-the-go-source-of-cue-https-cuelang-org-a-configuratio`  
Latest archive: `a5a8dc20-9355-4f80-9929-23b01e704bff_submission_2026-07-09T08_34_46.554Z.zip`  
Revisions in Dropbox: 1

## Task summary

`/app` is the Go source of [CUE](https://cuelang.org), a configuration and constraint language: it reads configuration source text, unifies the constraints that text declares, and either produces an evaluated result or reports a **conflict** when a value is required to be two incompatible things at once. It builds offline: ``` cd /app && go build ./... ```

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **medium** data-processing task (cue, configuration-language, constraint-solver, unification).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a5a8dc20-9355-4f80-9929-23b01e704bff_submission_2026-07-09T08_34_46.554Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
