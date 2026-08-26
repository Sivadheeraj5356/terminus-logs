# Numeric field notes

Probe vector uses pack seed x_seed from meta.toml and dimension dim.
Each component x at index i takes value one plus one tenth of ((i plus x_seed) mod 97).

Reference product y_ref comes from the pack mathematical matrix under full-storage semantics (half packs imply missing lower entries mirror the upper) times x.

Residual r_abs is the Euclidean length of the vector difference between y and y_ref.
Residual r_rel is r_abs divided by the greater of the Euclidean length of y_ref and 1e-300.

Pack meta.toml fields abs_band and rel_band bound r_abs and r_rel.
Pack field nz_stored means the count of nonzero entries kept on disk for that pack before expand.

Half packs also require the product from the expanded live view to agree with full-storage y_ref within expand_match_tol from nlim.toml on the Euclidean difference.

## slot_map.json

- field pack_id means the pack directory name
- field dim means the matrix dimension
- field nz_live means the count of stored nonzero entries in the live view used by the probe
- field nz_cap means the nz_cap value from nlim.toml
- field view_digest is computed as sha256 hex over little-endian f64 values, then u32 column ids, then u32 row pointers from the live view

nz_live must stay at or under nz_cap.

## band_tbl.json

- fields pack_id, r_abs, r_rel, abs_band, rel_band
- field trace_digest is computed as sha256 hex of ASCII lines pairing index i with y[i] rounded to 12 decimal places

## run_log.jsonl

run_log.jsonl uses JSON Lines (jsonl). One JSON object per successful probe with keys
pack_id, nz_live, r_abs, r_rel, trace_digest, ts_mono.

field ts_mono means a non-decreasing integer millisecond counter local to the process.
