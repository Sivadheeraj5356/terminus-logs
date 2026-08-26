# # Shared-library relocation witness normalization

- **UUID:** `ee87653e-b083-4306-a269-17b7ee20d3cb`
- **Slug:** `shared-library-relocation-witness-normalization`
- **Category:** security
- **Difficulty:** hard

## Summary

Release engineering teams shipping prebuilt .so artifacts into regulated fleets depend on ld.so loading relocation tables that match the sealed dependency graph. Some vendor toolchains emit non-standard dynamic relocation encodings—cipher-scrambled r_info fields or GMRL envelope-packed section headers—that break dynamic linking even when symbol names look correct.

Relbind (/app/bin/relbind) is the offline witness normalizer already wired into the Makefile tree. Agents build out this relocation witness normalization subsystem: finish the C++ kernels so relbind reads a candidate shared object, classifies its encoding profile, rewrites .rela.dyn and .rela.plt in place, and preserves every byte outside those sections.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
