# # Shared-library relocation witness normalization

Submission: `ee87653e-b083-4306-a269-17b7ee20d3cb`  
Slug: `shared-library-relocation-witness-normalization`  
Latest archive: `ee87653e-b083-4306-a269-17b7ee20d3cb_submission_2026-07-16T16_54_24.112Z.zip`  
Revisions: 1

## Task summary

Release engineering teams shipping prebuilt .so artifacts into regulated fleets depend on ld.so loading relocation tables that match the sealed dependency graph. Some vendor toolchains emit non-standard dynamic relocation encodings—cipher-scrambled r_info fields or GMRL envelope-packed section headers—that break dynamic linking even when symbol names look correct. Relbind (/app/bin/relbind) is the offline witness normalizer already wired into the Makefile tree. Agents build out this relocation witness normalization subsystem: finish the C++ kernels so relbind reads a candidate shared object, classifies its encoding profile, rewrites .rela.dyn and .rela.plt in place, and preserves every byte outside those sections. After normalization, /app/bin/test_runner dlopen-loads the same library to confirm dynamic linking succeeds.

Required artifacts include: `/app/bin/relbind`, `/app/bin/test_runner`, `/app/docs/relbind-refusal-envelope.md`, `/app/data/binaries/`, `/app/docs/encoding-policy.md`, `/app/docs/witness-bind-contract.md`, `/app/docs/trust-envelope-charter.md`, `/app/docs/reloc-witness-lifecycle.md`.

Author anonymous tagged this **hard** security task (elf, relocation, attestation, trust, binary-analysis, witness, security).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `ee87653e-b083-4306-a269-17b7ee20d3cb_submission_2026-07-16T16_54_24.112Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
