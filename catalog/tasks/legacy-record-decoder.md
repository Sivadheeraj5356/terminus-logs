# # Legacy Record Decoder

Submission: `ddff1202-d652-4e57-b812-a686e3c2e739`  
Slug: `legacy-record-decoder`  
Latest archive: `ddff1202-d652-4e57-b812-a686e3c2e739_submission_2026-07-09T09_38_57.095Z.zip`  
Revisions: 2

## Task summary

The decoder at `/app/environment` reads paired binary dumps and text exports, compares them for compatibility, and writes a validated bundle to `/app/output/legacy_record_bundle.json`. The pipeline is currently broken: decoded pairs are misreported as compatible when they diverge, malformed binary records pass silently instead of being flagged, and field extraction from the binary format is incorrect. Fix the source under `/app/environment/src` and `/app/environment/tools` so the normal build-and-run sequence regenerates a correct bundle. The decoy modules ending in `_stub.rs` are alternate paths not on the active decoder. Run `/app/environment/scripts/build_all.sh`, then execute the xscope checker documented in `/app/environment/docs/notes.md`. If local state becomes dirty, run `/app/environment/scripts/clear_scratch.sh` before retrying.

Required artifacts include: `/app/environment`, `/app/output/legacy_record_bundle.json`, `/app/environment/src`, `/app/environment/tools`, `/app/environment/scripts/build_all.sh`, `/app/environment/docs/notes.md`, `/app/environment/scripts/clear_scratch.sh`.

Author anonymous tagged this **hard** data-processing task (rust, reverse-engineering, file-format, serialization, compatibility, data-processing).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 1200s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ddff1202-d652-4e57-b812-a686e3c2e739_submission_2026-07-09T09_38_57.095Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
