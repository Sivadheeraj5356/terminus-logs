# roundtrip.md — round-trip witness plane

Authoritative for the `roundtrip_witness` top-level scalar in
`/app/src/results.json`. This is the fourth independent proof plane
alongside `policy_witness`, `salt_witness`, and `variant_witness` — it
binds every entry to a decoder-side check that the emitted Fibonacci
codeword actually decodes back to the entry's `n`.

## Per-entry round-trip

For every entry in `decoded` the driver computes a pair
`(roundtrip_ok, bit_len)`:

- `variant == "unknown"` → force `roundtrip_ok = false`, `bit_len = 0`.
  Unknown-variant fixtures never carry a decodable codeword; they must
  register as a round-trip miss in the witness so a hardcoded
  all-successful witness does not slip past.
- otherwise decode `fibonacci_code` under its `variant`, run the
  resulting Zeckendorf index list through
  `crate::zeckendorf::zeckendorf_sum`, and compare against `n`.
  - Match → `roundtrip_ok = true`, `bit_len = len(fibonacci_code)`.
  - Decode failure or mismatch → `roundtrip_ok = false`,
    `bit_len = 0`.

`bit_len` is 0 whenever `roundtrip_ok` is false so a failing entry
cannot smuggle a spurious length claim into the aggregate.

Neither `roundtrip_ok` nor `bit_len` is emitted per-entry in
`results.json`. Both live inside the driver's internal projection only.
The witness itself is the aggregate.

## Aggregate

    roundtrip_records = sorted(
        [ {"bit_len": <int>,
           "name":    "<stem>",
           "roundtrip_ok": <bool>}
          for every entry in decoded ],
        key = "name"
    )
    roundtrip_witness = SHA-256( canonical_json(roundtrip_records) )

Canonical JSON of the list follows the same rules used by every other
plane: keys sorted lex-ascending (`bit_len < name < roundtrip_ok`), no
whitespace between tokens, no trailing newline. Integers as bare
decimals, strings quoted, booleans `true` / `false`.

Because `decoded` is already sorted ascending by name, iterating
`decoded` in order produces the required sort — an implementation that
walks `decoded` linearly and appends does not need a separate sort
pass.

## Composed decoder

The batch driver's per-entry check composes `fibonacci_decode` from
`crate::fibonacci_code` with `zeckendorf_sum` from
`crate::zeckendorf`. That composition is the natural home for
`fibonacci_decode_n(bits, variant) -> Option<u64>`. See
`fibonacci_code.rs` for the shipping signature. `fibonacci_code.rs`
MUST use `crate::zeckendorf` for that composition — the composed
decoder is the required call site.

## Chain participation

`roundtrip_witness` participates in `chain_sha256` at its lex-sorted
position among the five witness planes:

    codeword < policy < roundtrip < salt < variant < wythoff

so the chain input is per-entry SHAs followed by `codeword_witness`,
`policy_witness`, `roundtrip_witness`, `salt_witness`, and
`variant_witness` in that order. See `witnesses.md §chain_sha256` for
the concatenation and `witnesses.md §Top-level shape` for the extended
key set.

Perturbing `roundtrip_witness` changes `chain_sha256`. A driver that
forgets to fold this plane into the chain input passes the older
three-plane tests but fails
`test_roundtrip_witness_participates_in_chain_sha256`.
