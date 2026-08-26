# Inclusion and digest notes

Structured constants live in companion file `math_b.toml`. Fold semantics,
journal live selection, cache sealing, rotation remaps, and nest bias are split
across `data/wal44/NOTE.txt`, `data/annex44/NOTE.txt`, and `duty_c.md`.

Graded fields `digest_hex`, `alg_keys`, `nest_span`, `nest_depth`, `script_rows`,
`cite_pairs`, `rot_arms`, and `run_digest` must stay coherent with those
obligations after a published cold regeneration. Warm restarts are valid only
when the stored fingerprint and seal equal the freshly computed live pair.
