# Our offline-first editor at `/app` replicates text edits through an RGA sequence

Submission: `2bdcc36d-dc9f-4ec3-bd26-27bdee0c46ba`  
Slug: `our-offline-first-editor-at-app-replicates-text-edits-throug`  
Latest archive: `2bdcc36d-dc9f-4ec3-bd26-27bdee0c46ba_submission_2026-07-05T14_38_36.911Z (2).zip`  
Revisions: 4

## Task summary

Our offline-first editor at `/app` replicates text edits through an RGA sequence CRDT. Each replica maintains a Merkle DAG over its operation log with embedded vector clocks for diff-based anti-entropy, but partitioned replicas stop converging and concurrent inserts at the same anchor disagree on document order. Bring `/app/src/merkle.rs`, `/app/src/sync.rs`, and `/app/src/sequence.rs` into compliance with `/app/spec/merkle_contract.md`, `/app/spec/sync_protocol.md`, and `/app/spec/sequence_crdt.md`. Compliance means the Merkle layer builds a balanced OpId-ordered tree with contract-correct hashing and minimal `diff_paths` (including the leaf-vs-internal shape case in the Merkle spec); sync helpers reconcile divergent DAGs via diff → export → import and deduplicate operation logs sorted by full `OpId`; and the sequence CRDT orders concurrent siblings and materializes documents by full `OpId`, not counter alone. All `scenetest` scenarios must pass.

Required artifacts include: `/app/src/merkle.rs`, `/app/src/sync.rs`, `/app/src/sequence.rs`, `/app/spec/merkle_contract.md`, `/app/spec/sync_protocol.md`, `/app/spec/sequence_crdt.md`, `/app/src/bin/scenetest`, `/app/src/sim.rs`.

Author anonymous tagged this **hard** build-and-dependency-management task (crdt, merkle-tree, distributed-systems, vector-clocks, sync).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `2bdcc36d-dc9f-4ec3-bd26-27bdee0c46ba_submission_2026-07-05T14_38_36.911Z (2).zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
