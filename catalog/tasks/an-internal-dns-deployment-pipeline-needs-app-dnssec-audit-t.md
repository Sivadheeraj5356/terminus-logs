# An internal DNS deployment pipeline needs `/app/dnssec-audit` to decide whether 

Submission: `9353db02-8890-4cf8-94fb-b5eaacb85392`  
Slug: `an-internal-dns-deployment-pipeline-needs-app-dnssec-audit-t`  
Latest archive: `9353db02-8890-4cf8-94fb-b5eaacb85392_submission_2026-07-16T09_20_21.428Z (1).zip`  
Revisions in Dropbox: 3

## Task summary

An internal DNS deployment pipeline needs `/app/dnssec-audit` to decide whether a child-zone delegation can be admitted without contacting the network. Complete the Go implementation in `/app` so the command reads one JSON bundle from the file named by its optional argument, or from standard input when no argument is supplied, and writes exactly one JSON object containing `admit` and `reasons`. The detailed bundle schema and the canonical DNSSEC subset used by this pipeline are documented in `/app/POLICY.md`; that file is the behavioral authority for this task. Admission requires a supported parent DS to authenticate an eligible child DNSKEY and every supplied RRset to have a currently valid signature from an authenticated zone key. Treat DNS names, DNSKEY key tags, DS digests, canonical RRset ordering, signer and wildcard scope, algorithm policy, and signature time windows exactly as the policy describes. A successful result is `{"admit":true,"reasons":[]}`. A rejected bundle must set `admit` to false and return the distinct applicable reason codes in lexicographic order; malformed input must be rejected rather than causing a panic. Keep the implementation self-contained in Go and preserve both file-argument and stdin operation.

Required artifacts include: `/app/dnssec-audit`, `/app/POLICY.md`.

Author anonymous tagged this **hard** security task (cryptography-encryption, digital-signatures-verification, dnssec, trust-chains).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `9353db02-8890-4cf8-94fb-b5eaacb85392_submission_2026-07-16T09_20_21.428Z (1).zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
