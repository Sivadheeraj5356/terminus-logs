# Deterministic RNG and initial assignment

The sampler draws all randomness from a single 64-bit xorshift64* generator seeded with `seed` from the configuration. The state starts equal to `seed` (or to the constant 0x9E3779B97F4A7C15 when the seed is zero). Each step transforms the state and returns a 64-bit output:

    x = state
    x = x XOR (x >> 12)
    x = x XOR (x << 25)     (evaluated modulo 2^64)
    x = x XOR (x >> 27)
    state = x
    output = (x * 0x2545F4914F6CDD1D) modulo 2^64

A uniform double in the half-open interval [0, 1) is produced from one output by taking its top 53 bits: `uniform = (output >> 11) * (1.0 / 2^53)`, where `2^53 = 9007199254740992`.

Initial topic assignment walks the corpus in canonical order: documents ascending by `doc_id`, and within each document token positions ascending. For each token occurrence, draw one generator output and assign topic `output modulo K`, where `K` is the configured topic count. Every initial assignment is immediately reflected in the count ledger (see `count-ledger.md`). Each initialized token consumes exactly one generator step.
