# codeword.md — codeword_witness proof plane

`codeword_witness` is the fifth witness plane emitted by the batch
driver, added by the 2026-07-09 addendum. It binds `results.json` to the
structural shape of every emitted Fibonacci codeword.

## Recipe

For each entry in `decoded`, derive two scalars from the entry's
`fibonacci_code` string:

- `ones_count` — the number of `'1'` characters in the codeword.
- `tail_bit` — the last character of the codeword as a single-character
  string (`"0"` or `"1"`), or the empty string `""` when the codeword is
  itself empty (unknown-variant / bad-magic fixtures).

Then form

    codeword_records = sorted(
        [ {"name": "<stem>", "ones_count": <u64>, "tail_bit": "<str>"}
          for every entry in decoded ],
        key = "name"
    )
    codeword_witness = SHA-256( canonical_json(codeword_records) )

Canonical JSON: keys sorted at every depth (`name < ones_count <
tail_bit`), no whitespace between tokens, no trailing newline.

## Not per-entry

`ones_count` and `tail_bit` NEVER appear in per-entry `decoded` records
— they live only inside the plane. Emitting either as a per-entry field
mutates the per-entry canonical-JSON SHA and breaks the pinned entry
SHAs.

## Structural discipline

- Canonical fixtures satisfy `tail_bit == "1"` (the terminating-pair
  final bit is the MSB of the last Fibonacci coefficient's terminator).
- Reverse-msb fixtures satisfy `tail_bit == "1"` only when the
  Zeckendorf decomposition's low-index term is not `F_2`; otherwise the
  reversal places the terminator at the front and the tail carries the
  first significant bit. Either way, a driver that emits an all-zero
  codeword fails the pinned witness match.
- Unknown-variant fixtures satisfy `tail_bit == ""` AND `ones_count ==
  0` because the codeword is the empty string per
  `contracts/rejections.md §VariantUnknown`.

## Position in `chain_sha256`

`codeword_witness` lands FIRST among the witness planes in `chain_input`
(lex order `codeword < policy < roundtrip < salt < variant < wythoff`) — see
`witnesses.md §chain_sha256`. Tampering with the plane perturbs the
chain aggregate.
