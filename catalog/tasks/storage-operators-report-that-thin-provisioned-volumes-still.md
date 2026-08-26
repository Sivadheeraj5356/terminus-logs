# Storage operators report that thin-provisioned volumes still show high utilizati

Submission: `fea51224-f694-463a-9acb-3bb06d53d171`  
Slug: `storage-operators-report-that-thin-provisioned-volumes-still`  
Latest archive: `fea51224-f694-463a-9acb-3bb06d53d171_submission_2026-07-20T06_27_11.470Z.zip`  
Revisions: 2

## Task summary

Storage operators report that thin-provisioned volumes still show high utilization after trim replay exits zero. Guest trim logs discarded ranges, but chunk inventory exports show no reclaimable slot change. Array trim telemetry reports cleared extents while the volume free-map digest stays on a prior epoch. A second replay window fails convergence: trim transcripts, digests, propagation traces, checkpoint persistence, and staging revision disagree. Resuming after interrupting the first window leaves staging revision lagging the digest epoch despite a zero exit. Convergence requires every export surface to agree.

Required artifacts include: `/app/environment/config/trim_policy.toml`, `/app/environment/docs/export_contract.md`, `/app/environment`, `/app/bin/volutil`, `/app/output`, `/app/environment/scripts/repro_trim_cycle.sh`, `/app/output/trim_transcript.json`, `/app/output/slot_map_digest.json`.

Author anonymous tagged this **hard** system-administration task (thin-provisioning, discard, fstrim, storage, go, sysadmin).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 900s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `fea51224-f694-463a-9acb-3bb06d53d171_submission_2026-07-20T06_27_11.470Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
