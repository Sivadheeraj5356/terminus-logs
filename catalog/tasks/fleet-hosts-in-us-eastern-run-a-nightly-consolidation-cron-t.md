# Fleet hosts in US/Eastern run a nightly consolidation cron that keeps durable to

Submission: `e588172b-0e0e-4941-a274-ffdd969e443b`  
Slug: `fleet-hosts-in-us-eastern-run-a-nightly-consolidation-cron-t`  
Latest archive: `e588172b-0e0e-4941-a274-ffdd969e443b_submission_2026-07-20T16_49_40.826Z.zip`  
Revisions: 1

## Task summary

Fleet hosts in US/Eastern run a nightly consolidation cron that keeps durable totals under /var/lib/acct and rebuilds an offline daylight-saving schedule history into /app/output/schedule_ledger.json. Disk, load, and cron.service probes stay green, but after local clock transitions the recorded schedule no longer matches what operators expect. Window indexes live under /app/data/windows/{backward,forward,resume}/window.conf (passed to step_tool as --env), fragment snapshots live under /app/data/traces, and the host-side rebuild helpers and policy sources live under /app/environment (including shared cadence settings in m5s/cadence_policy.conf). Around the autumn fall-back weekend, one calendar day sometimes shows two completed runs with the same YYYYMMDD day stamp but different wall-time offsets inside the repeated local hour, and stored totals run high. Around the spring forward weekend, the civil hour that never exists on the local clock (ten-digit YYYYMMDDHH) is missing from the packed history: there is no service error line, only a hole in that day's schedule. After an ordinary host reboot, catch-up sometimes re-runs intervals that were skipped on purpose during the transition and inflates totals again, while genuine post-boot gaps can stay empty on later resumes. A rebuild that looks clean on the first pass can still be wrong on a later resume once the boot-era marker already exists, and civil keys for the same calendar day must stay consistent with the finest hour-level key already recorded while earlier windows were stepped.

Required artifacts include: `/app/output/schedule_ledger.json`, `/app/data/windows/{backward,forward,resume}/window.conf`, `/app/data/traces`, `/app/environment`, `/app/tools/step_tool`, `/app/tools/pack_tool`, `/app/environment/docs/step_tool.md`, `/app/output/step`.

Author anonymous tagged this **hard** system-administration task (cron, timezone, dst, zoneinfo, host-scheduling).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `e588172b-0e0e-4941-a274-ffdd969e443b_submission_2026-07-20T16_49_40.826Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
