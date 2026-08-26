# Pack trace policy

## Profiles and capability modes

The bundled storage profiles are `silt`, `kite`, `rune`, and `dale`. Each profile runs under `cap_strict` and `cap_relaxed`.

## Graded artifact

`/app/output/pack_trace.json` from:

```bash
/app/environment/tools/rk_pack/rk_pack --matrix --out /app/output/pack_trace.json
```

Rebuild libraries first:

```bash
/app/environment/scripts/build_all.sh
```

## Schema

Top-level object with:

- `manifest_sha256` — lowercase hex sha256 over the concatenation of all row `prefix_digest`, `dev_digest`, and `replay_digest` strings in stable row order
- `rows` — array of exactly eight matrix rows (four profiles times two capability modes)

Each row contains:

- `public_id` — profile label (`silt`, `kite`, `rune`, `dale`)
- `cap_mode` — `cap_strict` or `cap_relaxed`
- `prefix_digest` — 64-char lowercase hex over linker cache bytes
- `dev_digest` — 64-char lowercase hex over device manifest bytes
- `replay_digest` — 64-char lowercase hex over the concatenation of the same linker cache bytes followed by the same device manifest bytes
- `size_bytes` — total packaging size for the row
- `gen_seal` — unsigned generation seal produced by root rebinding for that row

## Digest and seal rules

Linker cache bytes for a row are the ASCII bytes:

```text
PREFIX=<tree_prefix>
EPOCH=<epoch>
GEN=<gen_seal>
```

including the trailing newlines after each field. `tree_prefix` and `epoch` come from the profile definition under `/app/environment/prf_defs/`.

Device manifest bytes are:

1. one byte `node_count`
2. for each device index `0 .. node_count-1`, little-endian `uint16` major then little-endian `uint16` minor from the backend spec
3. trailing little-endian `uint32` equal to `gen_seal`

`prefix_digest` is sha256 over linker cache bytes. `dev_digest` is sha256 over device manifest bytes. `replay_digest` is sha256 over linker cache bytes concatenated with device manifest bytes.

Under `cap_strict`, rebinding must report readiness for strict packaging and `gen_seal` must be a positive odd integer. Under `cap_relaxed`, bind-only packaging is sufficient and `gen_seal` must be a positive even integer.

## Size classes

Per-profile byte ceilings are listed in `/app/environment/docs/size_ceilings.md`. Every row's `size_bytes` must be less than or equal to its profile ceiling.

## Staging arena and recovery

The checker keeps durable staging state at `/app/output/.pack_arena`. After a successful full matrix run the arena is marked dirty. A second matrix run without recovery must fail. Truncated or magic-corrupted arena state must also fail until restored.

Before re-running the checker after a packaging cycle, restore staging bytes idempotently:

```bash
/app/environment/migrations/mig_rst.sh --apply-base /app/environment/fx_bins/base/pack_base.bin
```

To inject a corrupt arena for recovery drills:

```bash
/app/environment/tools/arena_ctl/arena_ctl --corrupt
```

then apply the reset command above before grading.

## Packaging modules

Sources under `/app/environment/bx7/`, `/app/environment/lw3/`, and `/app/environment/dm5/` implement root rebinding seals, linker cache generation, and device manifest materialization. Module behavior must be correct so regenerated trace rows match the digest and seal rules—not only the rk_pack CLI output.

The platform verifier runs `/app/tests/test.sh` with pytest `--ctrf` logging. Recovery regression checks may also write `/app/output/seed1.json` and `/app/output/seed2.json`.

## Evidence surfaces

- Partial log tails: `environment/fx_bins/logs/`
- Backend minimal sets: `environment/dm5/spec_bins/`
- Interim tally rows: `environment/fx_bins/interim/q7_v9.json` exposes a `listing_totals` object keyed by profile label; these counts are diagnostic only and must not be hashed in place of graded digests
