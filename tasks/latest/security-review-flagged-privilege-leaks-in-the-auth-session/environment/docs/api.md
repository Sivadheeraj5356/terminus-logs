# Session authority API

## Build

```bash
/app/environment/scripts/build_all.sh
```

Produces `/app/environment/tools/sf_verify/sf_verify` and `/app/bin/sf_verify`.

## Authority checker CLI

```
sf_verify --matrix <name|all> --profiles <csv> --witness-out <path>
```

`--matrix all` expands circ_fence, rot_chain, clock_mix, and burst_cap.
Profiles `tight` and `loose` load authentication/authorization constants from `environment/presets/`.

## Authority modules

- `core/kz` session seal and token circulation (closes prior-gen admit privilege across skipped gens)
- `lane/ep` session lifetime latch (idle vs absolute privilege window)
- `lane/nx` concurrent session occupancy fold under generation fence
- `tools/sf_verify` matrix engine, epoch ledger writer, and integrity-backed terminal packer

Verifier-owned probes (not part of the agent build tree) link these libraries during grading.

Behavioral contracts live in `verify_contract.md`.

## Digests

Python helper `/app/environment/tools/digest_hex.py` exposes `sha256_hex` and `journal_tag` aligned with the witness digest scheme in `verify_contract.md`.
