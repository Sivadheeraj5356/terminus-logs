# The depot capability audit regressed during a broadcast replay and key-epoch rol

Submission: `4f49822b-f0b0-4cc4-b748-2a76e3d8670d`  
Slug: `the-depot-capability-audit-regressed-during-a-broadcast-repl`  
Latest archive: `4f49822b-f0b0-4cc4-b748-2a76e3d8670d_submission_2026-07-17T12_11_54.089Z.zip`  
Revisions: 1

## Task summary

The depot capability audit regressed during a broadcast replay and key-epoch roll. Operators now see different admission traces for equivalent pack orderings, stale session rows disappear across rebuilds, alias-presented tickets disagree with canonical subjects, and revocation clears do not always take effect at their visible row sequence. The working source tree is `/app/environment`. The normal pipeline is `bash /app/environment/ci/rebuild.sh` plus `/app/environment/bin/depot audit --pack <pack>`, with `/app/output/admission_trace.json` as the regenerated trace. The audit must preserve same-session history across invocations, recover the exported trace from persisted runtime state with the output file removed, and still keep independent sessions isolated. The trace includes session identifiers, row sequence numbers, and broadcast sequence numbers through the `session_id`, `session_seq`, and `seen_seq` fields. Static JSON, output-only work, test edits, wrapper-only shortcuts, and bypassing `depot` are insufficient.

Required artifacts include: `/app/environment`, `/app/environment/ci/rebuild.sh`, `/app/environment/bin/depot`, `/app/output/admission_trace.json`, `/app/environment/docs/kel_contract.md`.

Author anonymous tagged this **hard** security task (capability, revocation, delegation, least-privilege, audit-trace, epoch-floor).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `4f49822b-f0b0-4cc4-b748-2a76e3d8670d_submission_2026-07-17T12_11_54.089Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
