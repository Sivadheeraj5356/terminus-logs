# We need a deterministic link-plan utility for a build audit. Complete the intent

Submission: `1c73c5a9-6581-46cd-b50b-d4e940874793`  
Slug: `we-need-a-deterministic-link-plan-utility-for-a-build-audit`  
Latest archive: `1c73c5a9-6581-46cd-b50b-d4e940874793_submission_2026-07-07T06_51_40.122Z.zip`  
Revisions: 1

## Task summary

We need a deterministic link-plan utility for a build audit. Complete the intentionally incomplete Go program in `/app/src/main.go` so `/app/build.sh` creates `/app/arcplan`, then run `/app/arcplan /app/linkcase /app/link-report.json`. The starter currently handles only a small part of loose-object processing. The complete four-file contract is in `/app/link-model.md`: it includes transitive symbol aliases, strong and weak references, ordered `NEED` directives, normal/group/whole archive scans, COMDAT ownership, and provider precedence. In particular, `OBJ` must name a loose object; using an archive member there is malformed input and must exit `2`. The verifier may create additional valid inputs following the same contract, so do not specialize the program to `/app/linkcase`. The output is one JSON object with exactly these fields: integer `version` equal to `2`; string `status` (`ok` or `error`); arrays `selected_units`, `extracted_members`, `discarded_units`, `symbols`, `unresolved`, and `errors` with the exact element fields and ordering defined in `/app/link-model.md`; and string `plan_sha256`, computed from the exact canonical transcript defined there. Empty collections must be arrays, not `null`, canonical symbol names must be used throughout the report, and the digest must use the `sha256:` prefix plus lowercase hexadecimal.

Required artifacts include: `/app/src/main.go`, `/app/build.sh`, `/app/arcplan`, `/app/linkcase`, `/app/link-report.json`, `/app/link-model.md`.

Author anonymous tagged this **medium** build-and-dependency-management task (static-linking, archives, symbol-aliases, deterministic-digests).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `1c73c5a9-6581-46cd-b50b-d4e940874793_submission_2026-07-07T06_51_40.122Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
