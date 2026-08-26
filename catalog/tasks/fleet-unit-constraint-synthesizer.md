# # Fleet unit constraint synthesizer

Submission: `fdd2c545-ffae-43e4-8859-124485be6134`  
Slug: `fleet-unit-constraint-synthesizer`  
Latest archive: `fdd2c545-ffae-43e4-8859-124485be6134_submission_2026-07-09T13_39_26.238Z.zip`  
Revisions: 3

## Task summary

The fleet synthesizer under `/app/environment` turns a declarative manifest plus overlay files into a verified systemd unit bundle and a deterministic restart trace. The pipeline currently mis-merges policy layers, mis-maps list fields into unit files, mis-labels slice entries, and simulates restart ordering incorrectly. Repair the Rust resolver, Go emitters, Go trace simulator, and tarball packer so the normal rebuild path produces correct outputs. Run `bash /app/environment/scripts/build.sh` after source edits, then regenerate artifacts with:

Required artifacts include: `/app/environment`, `/app/environment/scripts/build.sh`, `/app/environment/scripts/fleet_pipeline.sh`, `/app/output/fleet_units.tar`, `/app/output/restart_trace.json`, `/app/environment/docs/unit_contract.md`, `/app/environment/docs/precedence_matrix.md`, `/app/environment/data/scenarios/`.

Author anonymous tagged this **hard** system-administration task (systemd, go, rust, fleet, config-synthesis).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `fdd2c545-ffae-43e4-8859-124485be6134_submission_2026-07-09T13_39_26.238Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
