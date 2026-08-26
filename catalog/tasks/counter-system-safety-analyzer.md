# # Counter-system safety analyzer

Submission: `9ad85ea2-4fc0-4cfb-893e-0ed39c0fa39e`  
Slug: `counter-system-safety-analyzer`  
Latest archive: `9ad85ea2-4fc0-4cfb-893e-0ed39c0fa39e_submission_2026-07-06T16_27_49.869Z.zip`  
Revisions: 1

## Task summary

`/app` contains a Go analyzer for counter systems — the model behind resource pools, work queues, and token schemes. It reads one job as JSON on stdin: a number of counters, rewrite rules that atomically consume and produce counter units, a start state, and a list of cover queries, each asking whether the system can ever hold at least the queried amounts on all counters simultaneously. It writes one verdict per query as JSON on stdout — a `covered` array of booleans in query order. Verdicts must be exact for reachability at any depth, and the analyzer must decide every conforming job in bounded time — including systems whose counters can grow without limit, where the reachable state space is infinite. On several such systems the current analyzer returns verdicts that are simply not the truth values defined by the contract: run the jobs under `/app/samples/` against the matching `.expected.json` files to see a system where it claims a combination is attainable that the rules can never actually produce. The complete contract — system semantics, the cover question, the exactness and termination obligations, and validation — is in `/app/docs/spec.md`, with the I/O schema in `/app/docs/output_schema.md` and terms in `/app/docs/glossary.md`. The specification defines what a correct verdict is, not how to decide it; finding a decision procedure that is simultaneously exact on unbounded systems and always terminating is the work. Make the analyzer produce exactly the specified verdicts for every conforming job and the malformed verdict `{"malformed": true}` otherwise — for...

Required artifacts include: `/app/samples/`, `/app/docs/spec.md`, `/app/docs/output_schema.md`, `/app/docs/glossary.md`, `/app/analysis/analysis.go`, `/app/main.go`, `/app/go.mod`, `/app/model/`.

Author anonymous tagged this **hard** scientific-computing task (go, state-spaces, safety-analysis, counters, termination).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `9ad85ea2-4fc0-4cfb-893e-0ed39c0fa39e_submission_2026-07-06T16_27_49.869Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
