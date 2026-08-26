# The security release authority uses an offline Rust attestation gate in `/app/ta

Submission: `c1be8239-61e2-4b2d-bb37-db4341796f0b`  
Slug: `the-security-release-authority-uses-an-offline-rust-attestat`  
Latest archive: `c1be8239-61e2-4b2d-bb37-db4341796f0b_submission_2026-07-21T12_38_09.904Z.zip`  
Revisions: 13

## Task summary

The security release authority uses an offline Rust attestation gate in `/app/task_file/logseal` to decide whether signed artifacts remain trustworthy under signer compromise, transparency-log failure, and dependency-amplified blast-radius scenarios. Implement the gate so it produces the deterministic security decision report defined in `/app/task_file/logseal_contract.md`, including evidence failures, resilience cuts, recovery certificates, and release-policy outcomes. Run the security gate as `cargo run --release --bin logseal -- <input_dir> <output_dir>`. It must read the eight evidence and policy files named in the contract from `<input_dir>`, create `<output_dir>` when necessary, and write exactly one file: `<output_dir>/report.json`. The runtime is offline and already contains the locked dependencies. Work only in `/app/task_file/logseal`; do not modify `/tests` or `/solution`. The security gate combines canonical signatures, Merkle evidence, additive gating, per-artifact cuts, and a recovery-aware global domain cut whose direct failures feed synchronous weighted dependency rounds. Every selected fleet cut must survive permitted restorations, compute adversarial recovery-breakpoint and worst-margin witnesses, and use nested robust tie-breaking while meeting three target 

Required artifacts include: `/app/task_file/logseal`, `/app/task_file/logseal_contract.md`.

Author Anonymous tagged this **hard** security task (rust, security, attestation, transparency-log, supply-chain).

Time estimates: expert ~300.0 min, junior ~1800.0 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `c1be8239-61e2-4b2d-bb37-db4341796f0b_submission_2026-07-21T12_38_09.904Z.zip` is a task submission, not a Harbor job. 13 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
