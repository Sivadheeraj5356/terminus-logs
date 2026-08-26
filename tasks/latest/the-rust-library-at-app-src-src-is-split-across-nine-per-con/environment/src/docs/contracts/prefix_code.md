# prefix_code.md — Fibonacci and Elias-gamma codewords

Authoritative for `fibonacci_code`, `fibonacci_code_variant`,
`fibonacci_decode`, `elias_gamma_code`, and `elias_gamma_decode`. The
two universal codes travel together in every entry — a decoder that
only knows one of them still validates.

## Fibonacci code (canonical)

Input: `indices = [k_1 < ... < k_m]`, the sorted Zeckendorf indices of
a positive integer `n_effective`.

- Length is exactly `k_m` bits.
- Position `i` (0-indexed) corresponds to Fibonacci index `i + 2`.
- Positions `k_j - 2` for each `k_j` in indices hold `'1'`; every
  other position in `0 .. k_m - 2` holds `'0'`.
- Position `k_m - 1` holds a **terminating `'1'`**. The two adjacent
  `'1'`s at positions `k_m - 2` and `k_m - 1` are the codeword-boundary
  marker that makes Fibonacci coding a prefix code.

Empty input → empty codeword.

The `indices` list ingested here must already be a valid Zeckendorf
decomposition; there is no `assert!` on non-consecutiveness in
`fibonacci_code`, but a caller that hands in a decomposition with
consecutive indices produces a bit string that no downstream Fibonacci
decoder will accept and is out of contract.

Examples:

    n_effective = 1  → indices [2]    → code "11"
    n_effective = 2  → indices [3]    → code "011"
    n_effective = 4  → indices [2, 5] → code "10011"
    n_effective = 10 → indices [3, 6] → code "010011"

## Variant-aware Fibonacci code

`fibonacci_code(indices)` emits the canonical codeword above.
`fibonacci_code_variant(indices, variant)` selects the ordering per
the frame's variant marker byte. See `variants.md` for the two
supported variants and the reversal recipe.

`fibonacci_decode(bits, variant)` is the inverse — parses a codeword
under the given variant and returns the Zeckendorf index list.

## Elias gamma code

Buried rule: `n == 0` encodes to the single bit `"0"`. This is NOT the
empty string that textbook Elias-gamma is undefined for — the fleet
pins the zero-value encoding to `"0"` so downstream length-summing
invariants stay monotone across bad-magic / unknown-variant entries.

For `n >= 1`: let `w = floor(log2(n)) + 1` (the bit width of `n`).
Emit `w - 1` zeros, followed by the binary representation of `n`
MSB-first, starting with its leading `'1'`. Total length is
`2 * w - 1`.

`elias_gamma_code` does NOT branch on the variant marker — the
Elias-gamma companion emits identically under `canonical` and
`reverse-msb`. See `variants.md` §Elias-gamma is variant-agnostic.

Examples:

    n = 0  → "0"       (buried rule; NOT empty string)
    n = 1  → "1"       (w = 1 → 0 zeros + "1")
    n = 2  → "010"     (w = 2 → 1 zero + "10")
    n = 4  → "00100"
    n = 5  → "00101"
    n = 10 → "0001010"

`elias_gamma_decode(bits)` inverts the above — recognises the `"0"`
sentinel for `n == 0` and unwinds the unary-length + binary payload
otherwise.

## ZKDF frame + salt XOR + variant marker

Every fixture is a framed record, not raw JSON:

    bytes 0..4       magic, ASCII "ZKDF"
    bytes 4..12      salt, little-endian u64
    bytes 12..13     variant marker byte (see variants.md)
    bytes 13..end    JSON payload `{"n": <non-negative integer>}`

Before Zeckendorf-decomposing, derive the effective integer:

    n_effective = raw_n XOR (salt AND 0x7FFFFFFFFFFFFFFF)

Every downstream computation uses `n_effective`, not `raw_n`. Magic
mismatch (bytes 0..4 != "ZKDF") produces `n_effective = 0`. Unknown
variant marker (byte at offset 12 is neither `0x00` nor `0x01`) also
produces `n_effective = 0` — see `variants.md §Unknown-variant
handling`.
