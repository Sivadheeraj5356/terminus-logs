# witnesses.md — results.json shape, witness planes, chain_sha256

Authoritative for the emitted `/app/src/results.json`. Every field,
every witness plane, and the chain aggregate.

## 1. Top-level shape

Canonical JSON — keys sorted lexicographically at every depth, no
whitespace between tokens, no trailing newline byte. Top-level keys
are exactly **nine** (added `wythoff_witness` on 2026-07-10):

    { chain_sha256, codeword_witness, decoded, policy_witness,
      roundtrip_witness, salt_witness, variant_witness, witness,
      wythoff_witness }

Note the lex order at the tail: `witness` (the aggregates block) sorts
BEFORE `wythoff_witness` because `wi` < `wy`.

Entry keys, sorted (unchanged):

    { elias_gamma_code, fibonacci_code, is_prime, n, name, phi_p,
      phi_q, variant, zeckendorf }

`decoded` is sorted ascending by `name` (the fixture stem). Each
entry's `n` field is `n_effective`, not the raw JSON payload integer.

Witness aggregates, sorted (unchanged):

    { max_index, prime_count, prime_pi_100, total_bits,
      total_elias_bits, total_indices, total_ones }

- `max_index` — largest Fibonacci index used across all decompositions
  (0 if every input is 0).
- `total_bits` — sum of `len(fibonacci_code)` across `decoded`.
- `total_ones` — sum of `fibonacci_code.count('1')` across `decoded`.
- `total_indices` — sum of `len(zeckendorf)` across `decoded`.
- `total_elias_bits` — sum of `len(elias_gamma_code)` across `decoded`.
- `prime_count` — number of entries with `is_prime == true`.
- `prime_pi_100` — the prime-counting function π(100) computed at
  runtime via `crate::primes::prime_pi`. Fixed value `25` on this
  corpus (the corpus does not perturb π).

Neither `roundtrip_ok`, `bit_len`, `ones_count`, nor `tail_bit` appear
per-entry; each lives only inside its own witness projection. See
`roundtrip.md` and `codeword.md`.

## 2. salt_witness (frame-header plane)

An **independent** proof plane derived only from raw frame headers —
no dependency on the decoder.

    salt_records = sorted(
        [ {"magic_ok": <bool>,
           "name":     "<stem>",
           "salt":     <u64>,
           "variant_marker": <u8>}
          for every fixture in /app/src/fixtures/ ],
        key = "name"
    )
    salt_witness = SHA-256( canonical_json(salt_records) )

Canonical JSON of the list uses the same rules — keys sorted, no
whitespace. Bad-magic fixtures still appear in the list with
`magic_ok = false`. The raw `variant_marker` byte is preserved even
when the driver treats it as unknown.

## 3. variant_witness (variant-projection plane)

A third independent plane derived from the `{name, variant}`
projection of `decoded`:

    variant_records = sorted(
        [ {"name": "<stem>", "variant": "<label>"}
          for every entry in decoded ],
        key = "name"
    )
    variant_witness = SHA-256( canonical_json(variant_records) )

The variant label is `"canonical"`, `"reverse-msb"`, or `"unknown"`
per `variants.md`. This plane distinguishes a hardcoded
all-canonical decoder from one that consults the marker byte.

## 3b. roundtrip_witness (decoder-side plane)

A fourth independent plane derived by decoding each entry's Fibonacci
codeword back to an integer and comparing to `n`. See `roundtrip.md`
for the per-entry `(roundtrip_ok, bit_len)` recipe.

    roundtrip_records = sorted(
        [ {"bit_len": <int>, "name": "<stem>",
           "roundtrip_ok": <bool>}
          for every entry in decoded ],
        key = "name"
    )
    roundtrip_witness = SHA-256( canonical_json(roundtrip_records) )

Records keys sort lex-ascending: `bit_len < name < roundtrip_ok`.
`roundtrip_ok = false` and `bit_len = 0` for every `variant ==
"unknown"` fixture. Neither field is emitted per-entry in
`results.json`.

## 3c. codeword_witness (structural-shape plane)

A fifth independent plane derived from the emitted Fibonacci codeword's
`'1'` count and terminating character — see `codeword.md` for the full
recipe.

    codeword_records = sorted(
        [ {"name": "<stem>", "ones_count": <u64>, "tail_bit": "<str>"}
          for every entry in decoded ],
        key = "name"
    )
    codeword_witness = SHA-256( canonical_json(codeword_records) )

`tail_bit == ""` and `ones_count == 0` for every unknown-variant /
bad-magic fixture. Neither field is emitted per-entry in
`results.json`.

## 4. policy_witness (live-config plane) and chain_sha256

A sixth independent plane derived from the runtime policy file at
`/app/config/zeckendorf_policy.json`. Contracts §policy.md defines
the schema.

    policy_sha256 = SHA-256( raw bytes of /app/config/zeckendorf_policy.json )
    policy_witness_input = canonical_json({
        "cohort":               <policy.cohort>,
        "max_codeword_bits":    <policy.max_codeword_bits>,
        "policy_sha256":        <hex sha256 of raw policy bytes>,
        "policy_witness_salt":  <policy.policy_witness_salt>,
    })
    policy_witness = SHA-256( policy_witness_input )

The four keys are the ONLY keys in the witness input, sorted
lexicographically (`cohort < max_codeword_bits < policy_sha256 <
policy_witness_salt`).

## 3d. wythoff_witness (Wythoff Beatty-pair plane)

A sixth independent plane derived from the per-entry Wythoff Beatty
pair `(⌊n·φ⌋, ⌊n·φ²⌋)` via `crate::wythoff::wythoff_pair` — see
[`wythoff.md`](wythoff.md) for the recipe + integer-only requirement.

    wythoff_records = sorted(
        [ {"a": <u64>, "b": <u64>, "name": "<stem>"}
          for every entry in decoded ],
        key = "name"
    )
    wythoff_witness = SHA-256( canonical_json(wythoff_records) )

Neither `a` nor `b` is emitted per-entry in `results.json`.

## chain_sha256

The chain aggregate binds the decoded array to every witness plane:

    per_entry   = [ SHA-256(canonical_json(entry)) for entry in decoded_order ]
    chain_input = concat(per_entry)
                  || codeword_witness
                  || policy_witness
                  || roundtrip_witness
                  || salt_witness
                  || variant_witness
                  || wythoff_witness
    chain_sha256 = SHA-256( chain_input )

`chain_input` is the concatenation of hex strings — one 64-char
per-entry SHA per element of `decoded` (in `decoded` order), followed
by the six witness planes in **lex order** (`codeword < policy <
roundtrip < salt < variant < wythoff`). Every hex string is 64 chars.

Perturbing any per-entry SHA, any of the six witnesses, or their
ordering changes `chain_sha256`.
