# Branch tracker

Implement `trace_branch` in `/app/environment/src/continuation.cpp`. It is
currently a stub that returns nothing.

Two discretised boundary-value problems, each carrying a parameter `lambda`,
are fully specified in `/app/environment/docs/problem.md`. Each one's solution
set is a curve in `R^16`. Given a problem name, a branch selector `k`, and a
list of arclengths, `trace_branch` must return the point of the specified
branch at each requested arclength, measured along that branch from its start.

`/app/environment/src/main.cpp` already reads a contract file, calls
`trace_branch`, and writes the result; `scripts/run_all.sh` builds the project
and runs every case listed in `data/cases.csv`. Do not change the declared
signature of `trace_branch` in `include/continuation.hpp`.

Grading recomputes each requested point independently and compares it against
what you report, component by component, to a tight tolerance. Reporting a
point that solves the system but sits somewhere else on it — the wrong branch,
or the right branch at the wrong arclength — fails.

Write it from scratch in C++17. The standard library is available; no external
continuation, linear-algebra, or nonlinear-solver library is. Build with `make`
from `/app/environment`. The same executable is run against held-back
contracts, so nothing case-specific may be hardcoded.

Example: `./tracecurve data/contracts/c16.txt out.txt` writes one line per
requested arclength.
