# The dyeworks tool is a command-line reader at /app/environment/dyeworks that par

Submission: `61f6d0fd-74f9-480f-9c52-befa30a93887`  
Slug: `the-dyeworks-tool-is-a-command-line-reader-at-app-environmen`  
Latest archive: `61f6d0fd-74f9-480f-9c52-befa30a93887_submission_2026-07-18T06_31_23.271Z.zip`  
Revisions: 13

## Task summary

The dyeworks tool is a command-line reader at /app/environment/dyeworks that parses a compiled dyeworks-tree container and prints a one-line JSON summary for a file that conforms to the format. The summary is one line carrying exactly these keys in this order and nothing else: `version`, `dyeworksdefs_defined`, `nodes_parsed`, `lots_resolved`, `indirects_resolved`, and `root_type`, where `version` is the unit format version, `dyeworksdefs_defined` is the count of type declarations, `nodes_parsed` is the number of non-null nodes, `lots_resolved` and `indirects_resolved` are the counts of resolved lot references and indirect forms, and `root_type` is the type name of the root node. The byte layout is documented in /app/environment/docs/dyeworks-format.md. Every file under /app/environment/testdata/valid conforms to the format, and each must keep parsing and printing the same summary, with the same keys, order, and values. Your changes go in the C sources under /app/environment/src and the headers under /app/environment/include, and dyeworks stays the same compiled C reader; there is no network access, so do not install anything. The reader must accept exactly the files that conform to this format and turn away the rest. Every offset, size, count, and index a file carries is drawn from the file, so before the reader uses one it must confirm it against the file's real extent and against the structure the format says it names. A section conforms only when it lies wholly after the header and the section table and its length reaches no further than the bytes that follow its...

Required artifacts include: `/app/environment/dyeworks`, `/app/environment/docs/dyeworks-format.md`, `/app/environment/testdata/valid`, `/app/environment/src`, `/app/environment/include`.

Author anonymous tagged this **hard** security task (security, c, memory-safety, audit-and-patch, parser).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `61f6d0fd-74f9-480f-9c52-befa30a93887_submission_2026-07-18T06_31_23.271Z.zip` is a task submission, not a Harbor job. 13 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
