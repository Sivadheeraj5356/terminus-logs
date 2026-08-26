# A short secret message has been encrypted with a stream cipher whose keystream c

- **UUID:** `9fa4d98a-7392-42bc-80f9-4a8cec627a09`
- **Slug:** `a-short-secret-message-has-been-encrypted-with-a-stream-ciph`
- **Category:** security
- **Difficulty:** medium

## Summary

A short secret message has been encrypted with a stream cipher whose keystream comes from a linear congruential generator, and your job is to recover the message. Each challenge file describes one generator in a few key equals value lines.

It gives the modulus width in bits, a run of consecutive full width outputs the generator produced from its seed, the number of high order bytes taken from each later output to form keystream, and the ciphertext in hexadecimal. The modulus, the multiplier, and the increment are all secret, and the multiplier is never one.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
