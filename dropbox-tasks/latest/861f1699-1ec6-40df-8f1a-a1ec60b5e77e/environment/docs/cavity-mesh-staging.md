# Cavity mesh staging contract

After the CT speed map is built and before leapfrog integration, the assay must
persist a mesh staging certificate at:

`/app/state/<profile>/cavity_mesh.json`

Required fields:

- profile — CT stem
- nx, ny — grid dimensions
- air_cells — count of voxel value `0` (air cavity)
- wood_cells — count of voxel value `1` (wood shell)
- speed_digest — lowercase hex SHA-256 over comma-joined `%.6f` speed samples in
  row-major order
- protocol_epoch — integer lab epoch (currently `1`)

The leapfrog stage must refuse to proceed when the staging `speed_digest` does not
match a live recompute from the in-memory speed map. The spectral export binds
the same digest into `formants.json` as `cavity_speed_digest`.

Digest encoding matches `/app/environment/tools/cavity_digest_ref.py` (SHA-256 via
`hashlib` over `%.6f,` samples; CTB headers use little-endian `struct` packs).

Supplemental calibration volumes may appear under `/opt/verifier-fixtures`
(environment variable `TB3_FIXTURE_ROOT` when set). Extra CT stems live in
`tb3_ct` (for example `strad_ct.ctb` / profile `strad_ct`) and corresponding
batch reports under `tb3_out`. Staging and export digest bind rules are identical
to the bundled Amati and Guarneri stems.
