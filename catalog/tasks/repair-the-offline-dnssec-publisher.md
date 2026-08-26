# # Repair the offline DNSSEC publisher

Submission: `13fcabe4-60f7-4f19-9e85-f4f6a333e23e`  
Slug: `repair-the-offline-dnssec-publisher`  
Latest archive: `13fcabe4-60f7-4f19-9e85-f4f6a333e23e_submission_2026-07-16T12_56_04.191Z.zip`  
Revisions in Dropbox: 2

## Task summary

The offline publisher in `/app` produces inconsistent releases after interrupted DNSKEY rollovers and legacy snapshot imports. Repair the Go implementation shipped from environment sources into `/app`. Static or hand-written output is not sufficient; `/output/example.test.signed` and `/output/publication-manifest.json` must be produced by the normal publish pipeline through `/app/bin/zonepub`.

Required artifacts include: `/output/example.test.signed`, `/output/publication-manifest.json`, `/app/bin/zonepub`, `/app/README.md`, `/app/scripts/reset-workflows.sh`, `/app/scripts/repro.sh`.

Author anonymous tagged this **hard** security task (dnssec, offline-signing, crash-recovery, bind9, go).

Time estimates: expert ~480 min, junior ~1560 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `13fcabe4-60f7-4f19-9e85-f4f6a333e23e_submission_2026-07-16T12_56_04.191Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
