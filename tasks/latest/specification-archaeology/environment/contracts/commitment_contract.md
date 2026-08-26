# Commitment contract

`decision_commitment.bin` is raw bytes: ASCII `INC8821\0`, then three 32-byte SHA-256 digests in order: canonical `{"evidence": merged_evidence, "profile": profile}`, canonical trust assessment JSON, canonical containment plan JSON. JSON uses UTF-8, sorted keys, separators `,` and `:`, and `ensure_ascii=false`. No newline or hexadecimal encoding is present.
