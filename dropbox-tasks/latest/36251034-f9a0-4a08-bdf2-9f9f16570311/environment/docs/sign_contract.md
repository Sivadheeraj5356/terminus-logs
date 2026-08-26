# signing input

For each query, custodians sign the UTF-8 bytes of a single string built by joining these lines with `\n` (LF only, no trailing newline after the last line):

```
artifact-quorum-v1
{bundle_id}
{query_id}
{artifact_sha256_hex}
{scope}
{release_epoch}
{min_weight}
```

`release_epoch` and `min_weight` use decimal integer formatting without leading zeros. `artifact_sha256_hex` is lowercase hex exactly as carried in the query. Verification uses the custodian Ed25519 public key from the bundle and expects a 64-byte signature encoded as 128 lowercase hex digits.
