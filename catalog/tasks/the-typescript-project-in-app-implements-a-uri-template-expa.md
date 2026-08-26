# The TypeScript project in `/app` implements a URI Template expander that has to 

Submission: `d3ffba0a-6c5d-48ad-8195-543d5490bdb2`  
Slug: `the-typescript-project-in-app-implements-a-uri-template-expa`  
Latest archive: `d3ffba0a-6c5d-48ad-8195-543d5490bdb2_submission_2026-07-11T11_14_11.950Z.zip`  
Revisions: 2

## Task summary

The TypeScript project in `/app` implements a URI Template expander that has to satisfy the Level 4 template-expansion rules of RFC 6570. It consumes a single JSON object on standard input, shaped as `{"template": <string>, "variables": <object>}`, in which `variables` binds each name to a string, a list, or an associative object; it emits the fully expanded string on standard output, closed by one newline. A template that is not syntactically valid under RFC 6570 must not be expanded at all — the program prints the token `ERROR` and exits with a non-zero status. Compiling with `make` (a `tsc` build) yields the launcher `/app/uritmpl`, and that executable is what the standard uritemplate-test conformance vectors are run against. The expander must cover every RFC 6570 operator: the operator-less default plus `+`, `#`, `.`, `/`, `;`, `?`, and `&`, along with the prefix modifier `:N` and the explode modifier `*`. The `:N` prefix retains a string value's first `N` Unicode characters — the count is over characters, not bytes — before that portion is encoded, and it applies only to string values. Explode expands a list into repeated segments and expands an associative object into `name=value` pairs, so that exploding an object inside a query expansion emits separate `name=value` query parameters while the same object left unexploded flattens into one comma-joined run of alternating keys and values. An associative object's members are always emitted in the order the keys appear in the input JSON object, in both the exploded and the flattened form. For the named operators (`;`,...

Required artifacts include: `/app/uritmpl`.

Author anonymous tagged this **hard** data-processing task (uri-template, rfc-6570, expansion, url).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `d3ffba0a-6c5d-48ad-8195-543d5490bdb2_submission_2026-07-11T11_14_11.950Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
