# SPEC — redirect

The mathematical + serialization contract for the Zeckendorf batch
encoder has been split across `/app/src/docs/contracts/`. Read those
files first; they win over the seed's source-file comments if the two
disagree.

- `contracts/decomposition.md` — Fibonacci convention, top-down greedy
  decomposition, anti-hardcode rule.
- `contracts/canonical.md` — ascending index ordering, non-consecutive
  invariant, empty-case pinning, round-trip identity.
- `contracts/zeckendorf.md` — redirect stub + primality clauses +
  golden-ratio pair.
- `contracts/prefix_code.md` — Fibonacci and Elias-gamma codeword
  layout, ZKDF frame + salt XOR + variant marker byte.
- `contracts/variants.md` — canonical / reverse-msb / unknown variant
  profiles, `variant_witness` proof plane, unknown-variant handling.
- `contracts/roundtrip.md` — `roundtrip_witness` proof plane, composed
  decoder wiring.
- `contracts/witnesses.md` — `results.json` shape, witness aggregates,
  `salt_witness`, `policy_witness`, `variant_witness`,
  `roundtrip_witness`, `chain_sha256` composition.
- `contracts/policy.md` — `/app/config/zeckendorf_policy.json` schema
  and semantics.
- `contracts/rejections.md` — named rejection variants (`PolicyLoad`,
  `CodewordLengthCap`, `VariantUnknown`).

`INCIDENT_LOG.md` is the narrative history — the *why*, not the *what*.
