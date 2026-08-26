# Runtime env

- `WORKDIR=/app` (platform default)
- Optional `KVTILE_APP_ROOT` overrides the filesystem root for ledger, prior_seal, and default seal paths (default `/app`)
- Ledger path: `{KVTILE_APP_ROOT}/data/residency.bin`
- Prior fold file: `{KVTILE_APP_ROOT}/var/prior_seal.hex`
- Default seal path: `{KVTILE_APP_ROOT}/output/kvtile-residency-seal.json`
- No network at solve time
