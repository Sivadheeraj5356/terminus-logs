# The formal language in /app represents one arithmetic expression over IEEE 754 d

Submission: `595e7c67-ccaf-4544-8f5b-458174baba9b`  
Slug: `the-formal-language-in-app-represents-one-arithmetic-express`  
Latest archive: `595e7c67-ccaf-4544-8f5b-458174baba9b_submission_2026-07-17T15_58_04.720Z.zip`  
Revisions: 1

## Task summary

The formal language in /app represents one arithmetic expression over IEEE 754 double precision values. Its expressions contain number literals, the spellings inf and nan, free variables, unary minus, parentheses, and the binary operators plus, minus, times, and divide. The required artifact is a deterministic expression reducer that reads one program and emits the equivalent reduced program. The accepted syntax is defined by /app/docs/grammar.md, while /app/docs/semantics.md defines evaluation, permitted reductions, and canonical numeric rendering. These documents form the behavioral contract. Constant subexpressions are evaluated using double precision semantics. An operand may disappear only when doing so preserves the exact result for every possible double precision value of every free variable, including signed zero, infinities, and nan. Transformations must preserve the parsed expression structure whenever the contract does not authorize a reduction. Reassociation is not permitted. A surviving binary application is printed fully parenthesized, and the complete result is printed as exactly one canonical expression followed by a newline. The output must parse again under the same grammar and retain the specified meaning.

Required artifacts include: `/app/docs/grammar.md`, `/app/docs/semantics.md`, `/app/foldc`, `/app/src`, `/app/build.sh`.

Author anonymous tagged this **hard** scientific-computing task (constant-folding, ieee-754, signed-zero, floating-point, expression-rewriting).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `595e7c67-ccaf-4544-8f5b-458174baba9b_submission_2026-07-17T15_58_04.720Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
