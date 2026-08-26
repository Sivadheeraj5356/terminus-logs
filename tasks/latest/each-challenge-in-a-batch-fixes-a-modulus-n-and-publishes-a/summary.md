# Each challenge in a batch fixes a modulus `n` and publishes a list of rows, each

- **UUID:** `43df573d-66ad-483c-95df-96bc527959ce`
- **Slug:** `each-challenge-in-a-batch-fixes-a-modulus-n-and-publishes-a`
- **Category:** security
- **Difficulty:** hard

## Summary

Each challenge in a batch fixes a modulus `n` and publishes a list of rows, each row a triple `(e, f, c)`. Behind every challenge sit two secret integers, a message `m` and a mask base `s`, and a row that is authentic satisfies `c = m^e * s^f (mod n)`.

Not every published row is guaranteed to be authentic, the published values are not guaranteed to be written in canonical form, and neither `s`, nor the factorization of `n`, nor which rows are authentic is ever given; there is no decryption oracle. The message of a challenge is exactly `L` bytes big-endian, `L` is published with the challenge, and the first two bytes of that encoding are always `0xCA 0xFE`; the authentic rows together with that fixed header pin down `m` uniquely.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
