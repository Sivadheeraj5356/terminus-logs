# Remote attestation for our device fleet is fail-closed: a TPM2 quote cartridge m

Submission: `672694ec-c172-4fc4-a523-d3a64bf4e801`  
Slug: `remote-attestation-for-our-device-fleet-is-fail-closed-a-tpm`  
Latest archive: `672694ec-c172-4fc4-a523-d3a64bf4e801_submission_2026-07-21T05_47_00.999Z.zip`  
Revisions: 1

## Task summary

Remote attestation for our device fleet is fail-closed: a TPM2 quote cartridge must prove authenticity and measurement integrity before the device may be marked trusted. Reject forged ECDSA P-256 quotes, nonce replays, PCR digests that do not bind the event log, clock or counter rollback, unsafe clocks, disallowed firmware versions, and reference-measurement or event-order policy violations. Accept only evidence that authenticates and also satisfies the published appraisal rules. Evidence cartridges live under `/app/data`. Normative attestation, encoding, schema, and invocation contracts live under `/app/docs`. TPM 2.0-inspired grounding notes are under `/app/source_snapshots/README.md`.

Required artifacts include: `/app/data`, `/app/docs`, `/app/source_snapshots/README.md`, `/app/output/report.json`.

Author anonymous tagged this **hard** security task (tpm2, remote-attestation, pcr-integrity, event-log, ecdsa-quote, nonce-freshness).

Time estimates: expert ~480 min, junior ~960 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `672694ec-c172-4fc4-a523-d3a64bf4e801_submission_2026-07-21T05_47_00.999Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
