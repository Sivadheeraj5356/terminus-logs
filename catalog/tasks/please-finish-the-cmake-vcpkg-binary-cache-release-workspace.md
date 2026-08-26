# Please finish the CMake/vcpkg binary-cache release workspace in `/app`. Keep it 

Submission: `b04f54f7-6743-4105-9700-131fdf99731d`  
Slug: `please-finish-the-cmake-vcpkg-binary-cache-release-workspace`  
Latest archive: `b04f54f7-6743-4105-9700-131fdf99731d_submission_2026-07-17T03_45_35.119Z.zip`  
Revisions in Dropbox: 1

## Task summary

Please finish the CMake/vcpkg binary-cache release workspace in `/app`. Keep it fully offline: `/app/scripts/release.sh` and the `releasekit` binary must rebuild `/app/dist` from the current matrix, catalog, lock, dependency, and smoke inputs and produce the deterministic bundles, archives, manifest, checksums, and audit output defined in `/app/docs/vcpkg-release-contract.md`, `/app/docs/advanced-graph-contract.md`, `/app/docs/policy-contract.md`, and `/app/docs/data-dictionary.md`. Every bundled `bin/releasekit` must be the compiled Linux ELF produced by the locked Cargo release build, not a script or proxy. All configuration and smoke inputs are live release inputs. Derive every artifact from their current contents on every run; profiles, components, ordering, workspace metadata, and hashes are not fixed to the starter data. Direct audits and release-generated previews must implement the same public contract. Cargo is installed at `/usr/local/cargo/bin/cargo`, but callers may supply a `PATH` without that directory, so the launcher must establish its own Cargo path.

Required artifacts include: `/app/scripts/release.sh`, `/app/dist`, `/app/docs/vcpkg-release-contract.md`, `/app/docs/advanced-graph-contract.md`, `/app/docs/policy-contract.md`, `/app/docs/data-dictionary.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (offline-build, vcpkg, binary-cache, dependency-locking, reproducible-builds, policy-gates).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `b04f54f7-6743-4105-9700-131fdf99731d_submission_2026-07-17T03_45_35.119Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
