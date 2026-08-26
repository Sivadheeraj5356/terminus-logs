# Shared-library relocation witness normalization

Release engineering teams shipping prebuilt .so artifacts into regulated fleets depend on ld.so loading relocation tables that match the sealed dependency graph. Some vendor toolchains emit non-standard dynamic relocation encodings—cipher-scrambled r_info fields or GMRL envelope-packed section headers—that break dynamic linking even when symbol names look correct.

Relbind (/app/bin/relbind) is the offline witness normalizer already wired into the Makefile tree. Agents build out this relocation witness normalization subsystem: finish the C++ kernels so relbind reads a candidate shared object, classifies its encoding profile, rewrites .rela.dyn and .rela.plt in place, and preserves every byte outside those sections. After normalization, /app/bin/test_runner dlopen-loads the same library to confirm dynamic linking succeeds.

## Operational contract

Run make, then invoke relbind with one shared-library path followed by test_runner (/app/bin/test_runner) on the same path. Success means test_runner exits zero after relbind exits zero. Malformed inputs, truncated ELF headers, or unknown encodings must exit non-zero; stderr must carry refusal text documented in /app/docs/relbind-refusal-envelope.md.

Bundled witness corpora live under /app/data/binaries/ (libtarget_alpha.so, libtarget_beta.so, libtarget_gamma.so). Alpha objects need no mutation. Beta objects use XOR-scrambled relocation metadata. Gamma objects store GMRL-packed streams at the front of relocation sections.

## Specifications

Encoding profiles, cipher masks, and envelope byte layouts: /app/docs/encoding-policy.md.

In-place rewrite invariants (size, offset, zero-fill): /app/docs/witness-bind-contract.md.

Trust scope for third-party objects: /app/docs/trust-envelope-charter.md.

End-to-end witness lifecycle: /app/docs/reloc-witness-lifecycle.md.

Policy classification rules: /app/docs/relocation-trust-policy.md.

Kernel sources and headers live under /app/ in a modular layout. Decoy sources under /app/elf/ never participate in graded outputs.

Grading loads holdout_beta.so and holdout_gamma.so from tests/verifier-fixtures/ without bundled-path shortcuts. Pytest rebuilds relbind, exercises both binaries via subprocess, and validates relocation bytes with independent reference parsers rather than golden stdout strings.
