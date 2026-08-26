# Timeline naming after clock step-back

Submission: `896a541d-ead3-45b4-a24a-c1f548ab0594`  
Slug: `timeline-naming-after-clock-step-back`  
Latest archive: `896a541d-ead3-45b4-a24a-c1f548ab0594_submission_2026-07-11T11_53_18.331Z.zip`  
Revisions: 2

## Task summary

Timeline naming after clock step-back Fleet nodes show snapper timeline rows that disagree after an NTP step-back and warm restart. WAL batches arrived in directory listing order while checkpoint artifacts still claim an older handoff generation. Locale catalog excerpts and bind-mount alias rows look plausible in isolation until replay walks profiles out of catalog order.

Required artifacts include: `/app/environment`, `/app/output/timeline_resume_report.json`, `/app/environment/scripts/build.sh`, `/app/environment/scripts/replay_exec.sh`, `/app/environment/scripts/emit_exec.sh`, `/app/environment/config/replay_order.tsv`, `/app/environment/logs/`, `/app/environment/docs/precedence_notes.md`.

Author anonymous tagged this **hard** system-administration task (bash, snapper, btrfs, checkpoint, timeline).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `896a541d-ead3-45b4-a24a-c1f548ab0594_submission_2026-07-11T11_53_18.331Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
