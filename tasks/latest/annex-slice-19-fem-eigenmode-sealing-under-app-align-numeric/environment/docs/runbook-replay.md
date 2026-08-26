# Replay / tip hygiene

Resume only when tip is not stale, violations are zero, `table_hash` matches current authorities (calibration tables + clock + both band trees), tip `epoch_bind` matches `sha256(clock_bytes|table_hash)`, and `seal.bind` agrees with tip on bind, hash, and lineage.

A torn trailer on `mesh.wal` is compacted to intact CRC frames; lineage increments on rewrite. Idempotent rematerialize with resume disabled must preserve digests and chain digest.
