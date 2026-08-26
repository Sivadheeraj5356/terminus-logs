# build_dependency_toolchain

Submission: `f626bd08-a1fd-4033-a722-66c11c56b92f`  
Slug: `build-dependency-toolchain`  
Latest archive: `f626bd08-a1fd-4033-a722-66c11c56b92f_submission_2026-07-08T10_09_07.296Z.zip`  
Revisions: 2

## Task summary

The regression commits are listed in `/app/reports/regression_commits.txt`. Fix `/app/repo` so `go test ./...` passes again. The failures cross several packages — route matching, ledger persistence, dispatch ordering, and delivery retries all need to work together. A single `git revert` probably will not cut it because later commits sit on top of the broken code; repair the implementation on the current tip. Routes must match exactly (not by prefix or case folding), ledger writes must survive a reload, dispatch must keep submit order, and retried deliveries must not double-write.

Required artifacts include: `/app/reports/regression_commits.txt`, `/app/repo`.

Author anonymous tagged this **hard** build-and-dependency-management task (git, go, webhooks, relay, persistence, retry, bisect).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f626bd08-a1fd-4033-a722-66c11c56b92f_submission_2026-07-08T10_09_07.296Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Git history or refs are only partially repaired.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
