# policy.md — runtime policy file

Authoritative for `/app/config/zeckendorf_policy.json`. The batch driver
re-reads this file on every invocation before opening any fixture.

## Schema

Exactly three keys, no others. Canonical JSON — keys sorted
lexicographically, no whitespace, no trailing newline byte.

    {
        "cohort":               <string>,   // must equal "INC-2026-ZF1"
        "max_codeword_bits":    <integer>,  // in 1..=65536 inclusive
        "policy_witness_salt":  <string>    // opaque salt, mixed into policy_witness
    }

## Semantics

- `cohort` — pins the driver to a shipping cohort. The compiled binary
  refuses to run against a config whose cohort differs from
  `INC-2026-ZF1`. This is not a stylistic check; the archive team
  rotates cohort strings between runs to catch stale binaries.
- `max_codeword_bits` — hard cap on the length of any emitted Fibonacci
  codeword. When violated, the driver terminates with the
  `CodewordLengthCap` rejection (see §rejections.md). The cap is
  applied to `len(fibonacci_code)`, i.e. the bit count of the emitted
  Fibonacci codeword; it is not applied to the Elias-gamma companion
  and not to the count of Zeckendorf indices. Default value shipped in
  the seed policy is `4096`.
- `policy_witness_salt` — opaque string. Reserved as an extra input to
  `policy_witness` so the archive team can rotate witnesses across runs
  without touching binary code. Empty string is allowed but discouraged.

## policy_witness derivation

    policy_sha256 = SHA-256( raw file bytes of /app/config/zeckendorf_policy.json )
    input = canonical_json({
        "cohort":              policy.cohort,
        "max_codeword_bits":   policy.max_codeword_bits,
        "policy_sha256":       policy_sha256,
        "policy_witness_salt": policy.policy_witness_salt,
    })
    policy_witness = SHA-256( input )

The witness input is UTF-8 canonical JSON with keys sorted
(`cohort < max_codeword_bits < policy_sha256 < policy_witness_salt`),
integer values as bare decimals, string values quoted with `"`.

## Rotation

The interop harness rotates `max_codeword_bits` (and, less frequently,
`policy_witness_salt`) between runs. A driver that hard-codes any of the
three fields, caches the parsed policy across invocations, or embeds a
pre-computed `policy_witness` will fail the rotated fixtures.
