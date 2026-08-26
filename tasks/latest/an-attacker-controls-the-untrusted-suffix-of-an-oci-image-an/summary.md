# An attacker controls the untrusted suffix of an OCI image and is trying to escap

- **UUID:** `5df8652e-14e2-4067-9f02-680b00e711dc`
- **Slug:** `an-attacker-controls-the-untrusted-suffix-of-an-oci-image-an`
- **Category:** security
- **Difficulty:** hard

## Summary

An attacker controls the untrusted suffix of an OCI image and is trying to escape the extraction root or replace protected operating system files. Decide whether the image is safe by implementing the extraction security gate defined in /app/spec.

Create /app/layer_gate.c using only ISO C11 and the C standard library. Compile it with gcc -std=c11 -O2 -Wall -Wextra -Werror into /app/layer-gate.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
