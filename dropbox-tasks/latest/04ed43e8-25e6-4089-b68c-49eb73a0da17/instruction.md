Burst flock stampede

After a host power blip, bringing several dependent host units up in the same window sometimes leaves the published volatile workspace inconsistent: one coordinator reports active while a downstream job logs that the workspace marker is held busy. Starting each unit alone recovers cleanly. A rotation-heavy downstream log buffer hides earlier lines within minutes.

Repair the Go sources under `/app/environment` so the state-audit driver reproduces correct cross-authority evidence after parallel bring-up replays. Rebuild and invoke `/app/bin/state-audit` using the flags documented in `/app/environment/README.md`.

The grading pipeline deletes `/app/output/coordination_trace.json` and reruns the build-and-replay workflow; hand-written JSON is insufficient.

Fixture cycles under `/app/environment/fixtures/cycle` drive the replay matrix. Output schema, marker fingerprint rule (`marker_fp_host`, `marker_fp_peer`), staging lag rule, checkpoint epoch rule, lineage token rule, preservation stamp rule, and report_digest envelope are defined in `/app/environment/docs/coordination_contract.md`. Each run row includes scenario, slice_epoch, marker_fp_host, marker_fp_peer, hold_gap, staging_lag, checkpoint_epoch, lineage_token, preservation_stamp, and row_seal; global fields include runs, report_digest, and replay_token. Matrix-row completion rules and gate/journal ordering notes are in the same contract. Operator notes for the replay harness live in `/app/environment/README.md`.

To grade locally inside the container, run `bash /tests/test.sh`.
