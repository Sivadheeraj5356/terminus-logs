The regression commits are listed in `/app/reports/regression_commits.txt`. Fix `/app/repo` so `go test ./...` passes again.

The failures cross several packages — route matching, ledger persistence, dispatch ordering, and delivery retries all need to work together. A single `git revert` probably will not cut it because later commits sit on top of the broken code; repair the implementation on the current tip. Routes must match exactly (not by prefix or case folding), ledger writes must survive a reload, dispatch must keep submit order, and retried deliveries must not double-write.

Work from the tip of `main`, commit your changes, and leave a clean working tree with no uncommitted or untracked files.
