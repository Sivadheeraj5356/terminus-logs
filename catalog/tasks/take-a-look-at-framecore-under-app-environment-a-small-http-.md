# Take a look at framecore under /app/environment, a small HTTP/2 style transport 

Submission: `8579adc2-6377-4c10-a73c-d411a9be05a4`  
Slug: `take-a-look-at-framecore-under-app-environment-a-small-http-`  
Latest archive: `8579adc2-6377-4c10-a73c-d411a9be05a4_submission_2026-07-17T15_34_21.918Z.zip`  
Revisions in Dropbox: 1

## Task summary

Take a look at framecore under /app/environment, a small HTTP/2 style transport library. Its header memory accounting has drifted: every session tracks how many bytes and how many headers are currently charged against it from its streams, and every stream accumulates its own header block before handing it to the application layer. Session totals should reflect only what is still outstanding right now, never climb across idle traffic even across a stream's multiple phases, and a flood of minimally sized headers should not slip past the byte accounting cheaply. Streams also need to enforce which phase can follow which: informational phases only come before the one main headers phase, trailers only come last, and an out-of-order request must be turned away without disturbing the stream's current phase or accumulated block. Every legitimate case still has to work, including an empty-value header and anything sized, counted, or ordered exactly at a configured limit. The full contract, including the script format for exercising the code directly, is at /app/environment/docs/security-spec.md. g++ and make are preinstalled, build with make from /app/environment, there is no internet access. When done, write /app/environment/security_notes.md summarizing every subsystem changed, naming the relevant CWE classes, and noting the design is inspired by a real HTTP/2 implementation under the MIT license.

Required artifacts include: `/app/environment`, `/app/environment/docs/security-spec.md`, `/app/environment/security_notes.md`.

Author anonymous tagged this **hard** security task (security, resource-exhaustion, http2, session-memory-accounting).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 900s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8579adc2-6377-4c10-a73c-d411a9be05a4_submission_2026-07-17T15_34_21.918Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
