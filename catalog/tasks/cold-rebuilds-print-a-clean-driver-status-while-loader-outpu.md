# Cold rebuilds print a clean driver status while loader output still drops requir

Submission: `79664ae8-d24d-4937-bbce-87dff656db6b`  
Slug: `cold-rebuilds-print-a-clean-driver-status-while-loader-outpu`  
Latest archive: `79664ae8-d24d-4937-bbce-87dff656db6b_submission_2026-07-17T06_33_14.435Z.zip`  
Revisions: 3

## Task summary

Cold rebuilds print a clean driver status while loader output still drops required objects. Warm rebuilds look healthier, but manifest, journal, and loader surfaces disagree on ordering and availability. Incremental bundle deltas can be missing from regenerated `/app/output/` JSON on runs that looked successful. Carry sidecars from an earlier profile or merge tier can pin the wrong wave label across later driver invocations in the same session. Stamp digests and lane ranking also drift across shared helpers under `/app/environment/lib/`. Repair the bash pipeline under `/app/environment` so cold and warm profiles agree on object presence and ordering across `/app/output/staging_manifest.json`, `/app/output/phase_journal.json`, and `/app/output/loader_trace.json`. Regenerate those files through the driver under `/app/environment/driver/` for warm, cold, incremental merge, and second-tier merge wave shapes. Static or hand-written JSON under `/app/output/` is not enough. Do not mutate notes under `/app/environment/bundles/k6preserve/`.

Required artifacts include: `/app/output/`, `/app/environment/lib/`, `/app/environment`, `/app/output/staging_manifest.json`, `/app/output/phase_journal.json`, `/app/output/loader_trace.json`, `/app/environment/driver/`, `/app/environment/bundles/k6preserve/`.

Author anonymous tagged this **hard** system-administration task (initramfs, depmod, incremental-rebuild, early-boot, bash, offline).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `79664ae8-d24d-4937-bbce-87dff656db6b_submission_2026-07-17T06_33_14.435Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
