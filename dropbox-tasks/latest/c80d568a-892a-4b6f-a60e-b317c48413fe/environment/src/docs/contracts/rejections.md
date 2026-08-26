# rejections.md — named rejection variants and unknown-variant handling

Every rejection path in the batch driver emits a stderr line whose
first token is one of the names below, followed by `:` and a
diagnostic message. The verbatim spelling of each name is required —
the harness matches on the prefix token.

## PolicyLoad

`/app/config/zeckendorf_policy.json` failed to load, could not be
parsed as a JSON object, or had an unexpected field set. Exit code:
`2`.

Trigger conditions:

- File missing or unreadable.
- File is not UTF-8.
- Body is not a JSON object.
- Any required key (`cohort`, `max_codeword_bits`, `policy_witness_salt`)
  is missing.
- Any key beyond those three is present.
- `cohort` does not equal the compiled cohort constant `INC-2026-ZF1`.
- `max_codeword_bits` outside `1..=65536`.

## CodewordLengthCap

The Fibonacci codeword emitted for at least one fixture exceeded the
runtime cap. Exit code: `3`.

Trigger: `len(fibonacci_code) > policy.max_codeword_bits` for any
entry. The batch driver terminates on the first offending fixture and
does not write a partial `/app/src/results.json`. The stderr message
names the offending fixture stem and both the observed length and the
configured cap.

The cap is enforced against the emitted Fibonacci codeword (bits),
not the Elias-gamma codeword and not the number of Zeckendorf
indices. Under `reverse-msb` the codeword length is identical to the
canonical form, so the cap applies uniformly.

## VariantUnknown (per-entry, non-fatal)

The variant marker byte at frame offset 12 is neither `0x00`
(canonical) nor `0x01` (reverse-msb). This is NOT a fatal rejection —
the batch driver continues processing every other fixture — but the
affected entry ships with:

- `n = 0`
- `zeckendorf = []`
- `fibonacci_code = ""`
- `elias_gamma_code = "0"` (per `prefix_code.md §Elias gamma`)
- `is_prime = false`
- `phi_p = 0`, `phi_q = 0`
- `variant = "unknown"`

The raw marker byte is preserved in the `salt_witness` frame-header
plane so an independent recompute still classifies the fixture
correctly. See `variants.md §Unknown-variant handling`.

## Frame parse

The batch driver's frame/JSON parsers rely on `expect` on well-formed
inputs; on malformed input they panic with a message identifying the
fixture. This is not a named rejection variant — malformed fixtures
are a data-integrity problem, not a policy-boundary problem, and are
handled by the fixture-authoring pipeline upstream.
