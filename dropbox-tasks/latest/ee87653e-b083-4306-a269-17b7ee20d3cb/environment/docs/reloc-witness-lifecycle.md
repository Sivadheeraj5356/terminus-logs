# Relocation witness lifecycle

Relbind normalizes vendor shared libraries through three deterministic phases:

1. **Profile probe** — inspect .rela.dyn / .rela.plt bytes to classify Alpha, Beta cipher-masked, or Gamma envelope-packed encodings.
2. **Witness rewrite** — apply profile-specific transforms in place without shifting ELF layout.
3. **Load verification** — test_runner dlopen-exercises the normalized object to confirm dynamic linking succeeds.

Contracts: /app/docs/relocation-trust-policy.md, /app/docs/witness-bind-contract.md, /app/docs/encoding-policy.md.
