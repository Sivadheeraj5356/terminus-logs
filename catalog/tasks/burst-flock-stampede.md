# Burst flock stampede

Submission: `04ed43e8-25e6-4089-b68c-49eb73a0da17`  
Slug: `burst-flock-stampede`  
Latest archive: `04ed43e8-25e6-4089-b68c-49eb73a0da17_submission_2026-07-03T13_47_33.068Z.zip`  
Revisions in Dropbox: 1

## Task summary

Burst flock stampede After a host power blip, bringing several dependent host units up in the same window sometimes leaves the published volatile workspace inconsistent: one coordinator reports active while a downstream job logs that the workspace marker is held busy. Starting each unit alone recovers cleanly. A rotation-heavy downstream log buffer hides earlier lines within minutes.

Required artifacts include: `/app/environment`, `/app/bin/state-audit`, `/app/environment/README.md`, `/app/output/coordination_trace.json`, `/app/environment/fixtures/cycle`, `/app/environment/docs/coordination_contract.md`.

Author anonymous tagged this **hard** system-administration task (filesystem, flock, tmpfs, systemd-burst, go, frontier-hard).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1500s, verifier 700s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `04ed43e8-25e6-4089-b68c-49eb73a0da17_submission_2026-07-03T13_47_33.068Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
