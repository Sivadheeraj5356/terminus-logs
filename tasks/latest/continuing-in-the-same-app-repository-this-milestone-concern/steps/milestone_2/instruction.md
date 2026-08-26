Continuing in the same `/app` repository, this milestone concerns the seven `bvm`
subcommands that derive deeper analyses from a bytecode module.
`/app/docs/bvm-spec.md` remains the authoritative data contract for the type
lattice, the join (least-upper-bound) of stack and local types at control-flow
merge points, definite assignment of locals, and the exact output of every
command; `/app/data` holds a corpus of input modules to run the tool against.

The subcommands in scope are: `verify` (abstract-interpretation dataflow to a
fixpoint over each function's control-flow graph, printing a verified or rejected
verdict per function), `dom` (the immediate dominator of every reachable block),
`analyze` (reachable blocks, dead blocks and the maximum operand-stack depth),
`report` (a per-function summary followed by an FNV-1a digest), `run` and `trace`
(execution of `main` to a result or a trap), and `batch` (processing a manifest of
modules into per-model lines and a digest).

For every input there is exactly one correct output document. On some inputs the
current output diverges from what the specification defines. Correct the
implementation so that each subcommand produces exactly the specified output for
every module, then rebuild the binary with `go build -o /app/bin/bvm ./cmd/bvm`.
