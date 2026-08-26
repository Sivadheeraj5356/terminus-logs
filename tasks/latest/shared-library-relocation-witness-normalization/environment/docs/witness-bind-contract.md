# Witness bind contract

When relbind binds a relocation witness it must preserve these invariants:

1. **Size invariant** — total library byte length unchanged.
2. **Offset invariant** — section and program header offsets unshifted.
3. **Zero-fill invariant** — unused relocation section tail bytes set to `0`.
4. **Dual-section invariant** — both `.rela.dyn` and `.rela.plt` processed when present.

Alpha libraries are accepted without mutation. Beta libraries require cipher unmasking of each `r_info`. Gamma libraries require envelope unpacking into standard rows.

Verifier scratch paths may copy libraries to ephemeral names (`staging_snapshot.bin`, `truncated.so`, `fake.so`, `elf32.so`, `not_elf.txt`) or missing paths under `/tmp/nonexistent_file_12345.so` when exercising tamper refusal.
