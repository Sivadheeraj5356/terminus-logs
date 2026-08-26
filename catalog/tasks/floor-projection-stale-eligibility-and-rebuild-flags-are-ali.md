# Floor projection, stale eligibility, and rebuild flags are aligned, but `frontie

Submission: `49b48b21-5c4d-46b9-9dad-6e88538027b6`  
Slug: `floor-projection-stale-eligibility-and-rebuild-flags-are-ali`  
Latest archive: `49b48b21-5c4d-46b9-9dad-6e88538027b6_submission_2026-07-12T09_38_27.254Z.zip`  
Revisions: 1

## Task summary

Floor projection, stale eligibility, and rebuild flags are aligned, but `frontier_digest_hex` still drifts and runtime or manifest changes mid-session are not fully reflected in the rebuilt report. Third milestone: finish the rebuild path so `/app/scripts/frontier.sh` and `/app/launcher/lf_align` produce identical fixture-consistent output keyed by every consumer id in `/app/data/manifest.json` at rebuild time. Rechecks must pick up manifest rows and runtime settings changed during the session. Field summaries live in `/app/doc/frontier_fields.txt`; consolidation rules in `/app/doc/staleness_contract.txt`. Both entry points must emit the same report bytes for the same fixture state. Milestone 3 is complete when both rebuild entry points produce a fixture-consistent report keyed by every live manifest consumer. Signal milestone completion before advancing; the milestone test suite is the arbiter and no separate signal artifact is required.

Required artifacts include: `/app/scripts/frontier.sh`, `/app/launcher/lf_align`, `/app/data/manifest.json`, `/app/doc/frontier_fields.txt`, `/app/doc/staleness_contract.txt`.

Author anonymous tagged this **hard** data-processing task (lineage, dag, staleness, materialization, determinism, replay).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `49b48b21-5c4d-46b9-9dad-6e88538027b6_submission_2026-07-12T09_38_27.254Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
