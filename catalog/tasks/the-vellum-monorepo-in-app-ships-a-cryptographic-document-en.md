# The Vellum monorepo in `/app` ships a cryptographic document engine as a native 

Submission: `f1a3080e-1421-41d2-afc8-346c85bb1db8`  
Slug: `the-vellum-monorepo-in-app-ships-a-cryptographic-document-en`  
Latest archive: `f1a3080e-1421-41d2-afc8-346c85bb1db8_submission_2026-07-21T12_48_32.335Z.zip`  
Revisions: 1

## Task summary

The Vellum monorepo in `/app` ships a cryptographic document engine as a native library, a Python wheel, and a Node package for air-gapped qualification. The developer entry points `/app/scripts/dev-build` and `/app/scripts/dev-check` pass, but the release does not hold together. Running `/app/scripts/release --source-root <abs> --output <abs>` must write a complete bundle that satisfies `/app/docs/release-contract.md`. With the default output root the bundle lives at `/output/release` and contains the native library `/output/release/native/libvellum.so`, an installable Python wheel under `/output/release/python/`, an installable Node tarball under `/output/release/node/`, the dependency inventory `/output/release/metadata/dependency-inventory.json`, the signed provenance manifest `/output/release/metadata/provenance.json`, and the checksum manifest `/output/release/SHA256SUMS`.

Required artifacts include: `/app/scripts/dev-build`, `/app/scripts/dev-check`, `/app/scripts/release`, `/app/docs/release-contract.md`, `/output/release`, `/output/release/native/libvellum.so`, `/output/release/python/`, `/output/release/node/`.

Author anonymous tagged this **hard** build-and-dependency-management task (reproducible-builds, offline-packaging, cross-language-ffi, supply-chain, provenance).

Time estimates: expert ~420 min, junior ~1080 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `f1a3080e-1421-41d2-afc8-346c85bb1db8_submission_2026-07-21T12_48_32.335Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
