# ## Problem

Submission: `737acf18-05b5-4c2b-a6b9-42ddfd52315c`  
Slug: `problem-offline-workspace-builds-against-the-air-gapped-crate-mirror-fail-cargo`  
Latest archive: `737acf18-05b5-4c2b-a6b9-42ddfd52315c_submission_2026-07-18T21_08_29.440Z.zip`  
Revisions: 1

## Task summary

Offline workspace builds against the air-gapped crate mirror fail. `cargo build --offline --locked` cannot resolve or verify the packages listed for this lane even though crate tarballs appear present under the mirror trees. A discarded sync snapshot under `/app/data/mirror-stale` still looks plausible and must not be trusted as the active registry. Restore offline Cargo source replacement and the active local registry so the documented offline build succeeds for every primary package id. Stay offline (`allow_internet` is false). Hand-writing `target/` artifacts or a `vendor/` tree without going through Cargo does not pass: the verifier runs `cargo build --offline --locked` from `/app` and scores that toolchain result.

Required artifacts include: `/app/data/mirror-stale`, `/app/mirror`, `/app/docs/tgt_notes.txt`, `/app/Cargo.lock`, `/app/scripts/offline_build.sh`, `/app/docs/operator_notes.md`, `/app/mirror/`.

Author anonymous tagged this **hard** build-and-dependency-management task (rust, cargo, local-registry, lockfile, offline-build, registry-mirror).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `737acf18-05b5-4c2b-a6b9-42ddfd52315c_submission_2026-07-18T21_08_29.440Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
