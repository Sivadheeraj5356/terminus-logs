# Witness hash

atlas_witness is CRC32 over canonical sorted-key JSON of the atlas object excluding atlas_witness.

Canonical JSON rules:
- Object keys sorted lexicographically ascending
- No insignificant whitespace
- Strings JSON-escaped
- Booleans lowercase true/false
- Integers decimal without leading zeros

Digest format: eight lowercase hex digits (no 0x prefix). Pad on the left with zero characters when the CRC32 value is small so the digest is always exactly eight characters wide.
