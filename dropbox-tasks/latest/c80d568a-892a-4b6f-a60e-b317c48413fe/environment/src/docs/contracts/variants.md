# variants.md — encoding-variant profile

Two variant profiles are in force. Every `.json` ZKDF fixture declares
which one it exercises via a marker byte in the frame header at
offset 12 (see `prefix_code.md §ZKDF frame`). The batch driver MUST
select the correct Fibonacci-code ordering per fixture; a decoder that
ignores the marker and emits every codeword MSB-first passes canonical
fixtures but produces the wrong bit string for every reverse-msb one.

## Marker byte → variant

| Marker | Variant       | Fibonacci-code ordering          | Notes                          |
|-------:|---------------|----------------------------------|--------------------------------|
|   0x00 | `canonical`   | MSB-first per `prefix_code.md`   | Textbook Zeckendorf-Fibonacci  |
|   0x01 | `reverse-msb` | LSB-first (canonical reversed)   | In-house rotation profile      |

Any other marker byte triggers the `VariantUnknown` rejection (see
`rejections.md`) — the entry ships with `n = 0`, empty codewords, and
the `variant` field set to `"unknown"`.

## `reverse-msb` is NOT a public standard

The `reverse-msb` variant is the rotation's in-house Fibonacci-code
profile ratified after the June 2026 archive-interop hardening. It
shares the Zeckendorf decomposition of `canonical` (same indices, same
non-consecutive invariant) but pins the bit ordering to LSB-first —
the terminating `'1'` pair sits at the FRONT of the emitted string,
not the tail. `reverse-msb` is NOT in any public Fibonacci-coding
reference; a decoder must derive it from this contract.

Cryptographic hygiene: the reversal is applied AFTER the canonical
codeword is materialised, not by iterating indices in reverse — the
two are equivalent for well-formed Zeckendorf input but a decoder that
walks the indices backwards during emission tends to accidentally
break the terminating-pair invariant.

## Codeword layout per variant

For a Zeckendorf index set `S = [k_1 < ... < k_m]`, let `canonical(S)`
be the MSB-first codeword from `prefix_code.md §Fibonacci code`. Then:

    canonical    →  canonical(S)
    reverse-msb  →  canonical(S) reversed end-for-end

Length is `k_m` bits in both cases. The set of `'1'` positions in
`reverse-msb` is `{k_m - 1 - p : p in positions_one(canonical)}` —
still exactly `m + 1` bits set (the `m` Zeckendorf bits plus the
terminating boundary).

Examples (from `prefix_code.md §Fibonacci code`):

| n_effective | indices     | canonical | reverse-msb |
|------------:|-------------|-----------|-------------|
|           1 | `[2]`       | `11`      | `11`        |
|           2 | `[3]`       | `011`     | `110`       |
|           4 | `[2, 5]`    | `10011`   | `11001`     |
|          10 | `[3, 6]`    | `010011`  | `110010`    |

Note that `n = 1` produces the same string under both variants — the
one-bit reversal is a fixed point. Every fixture with more than one
Zeckendorf index distinguishes.

## Elias-gamma is variant-agnostic

The `elias_gamma_code` field on each entry does NOT depend on the
variant marker — the Elias-gamma companion emits identically under
`canonical` and `reverse-msb`. The variant marker gates only the
Fibonacci codeword ordering.

## Unknown-variant handling

When the variant marker byte is neither `0x00` nor `0x01`, the batch
driver treats the fixture equivalently to a bad-magic frame:

* `n = 0`
* `zeckendorf = []`
* `fibonacci_code = ""`
* `elias_gamma_code = "0"` (per `prefix_code.md §Elias gamma`)
* `is_prime = false`
* `phi_p = 0`, `phi_q = 0`
* `variant = "unknown"`

The entry still appears in `decoded` with the same field set as every
other entry — the driver does NOT emit a separate rejection shape.
Unknown-variant fixtures DO appear in `salt_witness` records with the
raw marker byte preserved.

## `variant_witness` proof plane

The batch driver emits a `variant_witness` top-level string in
`results.json`. It is the lowercase-hex SHA-256 of the canonical JSON of

    [
      {"name": "<basename>", "variant": "<label>"},
      ...
    ]

sorted lex-ascending by `name`. The `variant` label is `"canonical"`,
`"reverse-msb"`, or `"unknown"` (only when the marker byte is neither
0x00 nor 0x01).

`variant_witness` participates in `chain_sha256` at its lex-sorted
position (after `salt_witness`). See `witnesses.md`.

## Fixture coverage

Every fixture in the shipped corpus declares one of the three known
marker values in its byte at offset 12. A decoder that hard-codes
`canonical` for every fixture will pass the canonical fixtures but
MUST fail every `reverse-msb` fixture with a mirrored bit string — a
distinctive failure mode against the per-entry canonical-JSON SHAs.
