# Payload digest

`rebuild_digest` and `merge_digest` roll concatenated included payloads in first-seen merge order:

```
basis = 0xB0017000CAFEBABE
mult  = 137
for each byte b: h = (h * mult + b) mod 2^64
digest = h XOR len(concatenated payloads)
```

Format as 16 lowercase hex digits without prefix.
