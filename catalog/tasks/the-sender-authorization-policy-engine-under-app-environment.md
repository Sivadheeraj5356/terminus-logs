# The Sender Authorization Policy engine under /app/environment/engine is the

Submission: `47439143-dd47-4f4d-b1c5-c99786d26ac4`  
Slug: `the-sender-authorization-policy-engine-under-app-environment`  
Latest archive: `47439143-dd47-4f4d-b1c5-c99786d26ac4_submission_2026-07-16T13_14_58.819Z.zip`  
Revisions in Dropbox: 2

## Task summary

The Sender Authorization Policy engine under /app/environment/engine is the decision core of a mail anti-spoofing check: given a domain's published policy and a frozen DNS-like zone, it decides whether a connecting client IP is authorized to send mail for that domain. The semantics that policy is intended to have are written out in /app/environment/docs/sap-spec.md, and a few worked runs of the engine are in /app/environment/testdata/examples. The engine as deployed does not fully honour those semantics: on some queries it answers differently from the specification, authorizing a sender the policy meant to refuse, or refusing one it meant to admit. How many such places there are, whereabouts in the engine they sit, and whether they are independent of one another is for you to establish; assume nothing about their number or their shape, and note that on a given query more than one of them may bear on the answer at once. Your job is to implement the analyzer's decision, at /app/environment/analyzer/src/analyze.rs, so that for each query in a case file it reports three things: the result the deployed engine actually produces, the result the specification requires, and whether the two diverge. When they diverge, it also names the single settling token, as Part 2 defines. The exact case-file and certificate shapes are in the specification under Part 2.

Required artifacts include: `/app/environment/engine`, `/app/environment/docs/sap-spec.md`, `/app/environment/testdata/examples`, `/app/environment/analyzer/src/analyze.rs`, `/app/environment/analyzer/src/main.rs`.

Author anonymous tagged this **hard** security task (security, rust, authentication, email-spoofing, over-authorization, differential-analysis, audit).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `47439143-dd47-4f4d-b1c5-c99786d26ac4_submission_2026-07-16T13_14_58.819Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
