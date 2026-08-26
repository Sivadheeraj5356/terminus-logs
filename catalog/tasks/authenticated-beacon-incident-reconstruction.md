# # Authenticated Beacon Incident Reconstruction

Submission: `af9cf339-2a5e-442d-a69b-27154263704f`  
Slug: `authenticated-beacon-incident-reconstruction`  
Latest archive: `af9cf339-2a5e-442d-a69b-27154263704f_submission_2026-07-16T11_23_15.191Z.zip`  
Revisions: 1

## Task summary

This is an offline security-forensics and incident-reconstruction task. A monitoring station lost its trusted state after suspected telemetry forgery, replay, and cross-station credential misuse. Recover the final trusted sensor dataset from the remaining untrusted binary beacon stream without allowing damaged, stale, unauthenticated, or invalidated evidence to alter later security decisions. Produce a single C11 source file at `/app/src/beacon_replay.c`. The recovery host has only gcc and libc. The verifier compiles and runs it as:

Required artifacts include: `/app/src/beacon_replay.c`, `/app/beacon_replay`, `/app/spec/beacon_frames.md`, `/app/input_data/public_frames.bin`, `/app/input_data/public_frames.sha256`.

Author anonymous tagged this **hard** security task (security-forensics, telemetry-integrity, anti-replay, binary-evidence, crc32, credential-chains, authenticated-frames, digital-forensics, quorum-attestation, c).

Time estimates: expert ~600.0 min, junior ~3200.0 min.

Harbor timeouts: agent 1200.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `af9cf339-2a5e-442d-a69b-27154263704f_submission_2026-07-16T11_23_15.191Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
