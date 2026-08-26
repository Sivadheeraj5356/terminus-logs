# The `msgsigward` program under /app/environment is a complete RFC 9421 HTTP

Submission: `4e2fdfd9-59a3-4e50-b513-c2300b5e2399`  
Slug: `the-msgsigward-program-under-app-environment-is-a-complete-r`  
Latest archive: `4e2fdfd9-59a3-4e50-b513-c2300b5e2399_submission_2026-07-18T05_36_54.780Z.zip`  
Revisions: 6

## Task summary

The `msgsigward` program under /app/environment is a complete RFC 9421 HTTP message-signature verifier: `msgsig.Verify` in /app/environment/internal/msgsig/verify.go reads one immutable request bundle and prints the decision line `<verdict> <selector> <covered>` an HTTP server uses before acting on a signed request. The implementation is finished and builds, but it is **not** faithful to its specification: it contains several planted security defects, each a divergence from /app/environment/docs/security-spec.md that lets a forged, under-covered, replayed, body-substituted, or algorithm-downgraded request through — or misreports which rejection applies. The evidence is immutable: audit the code against the spec; do not modify the verifier or the tests. Your deliverable is /app/environment/findings.json. For **every** defect in the shipped verifier, include one *witness*: a complete request bundle (the same JSON schema `msgsigward` consumes, described in the spec's §1) on which the shipped verifier's decision is **insecure** — that is, it diverges from the decision the specification requires. A witness that makes the shipped verifier accept a request the spec rejects (a forgery slipping through), reject a request the spec accepts (a genuine request broken by a reconstruction error), or report the wrong rejection reason each expose a distinct defect. Cover them all; a findings file that misses any planted defect is incomplete.

Required artifacts include: `/app/environment`, `/app/environment/internal/msgsig/verify.go`, `/app/environment/docs/security-spec.md`, `/app/environment/findings.json`, `/app/environment/testdata/examples`.

Author anonymous tagged this **hard** security task (go, cryptography, http-message-signatures, rfc9421, signature-verification, algorithm-confusion).

Time estimates: expert ~240 min, junior ~540 min.

Harbor timeouts: agent 900s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `4e2fdfd9-59a3-4e50-b513-c2300b5e2399_submission_2026-07-18T05_36_54.780Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
