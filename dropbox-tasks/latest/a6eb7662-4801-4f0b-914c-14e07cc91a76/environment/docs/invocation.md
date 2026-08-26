# Invocation

Binary: /app/bin/assay-ledger

| Mode | Behavior |
|------|----------|
| (default) or analyze | Full load → evaluate → write snapshot → publish outputs |
| check-coin \<id\> | Same evaluation for one coin; print JSON detail for that coin to stdout; still refresh snapshot and outputs for the full catalog |
| export | Publish outputs from existing snapshot only; exit 2 if snapshot missing |
| version | Print assay-ledger 1.0.0 and a trailing newline |

Environment overrides (absolute paths only):

- TB3_ASSAY_CONFIG → assay-config.json
- TB3_COINS → coins.json
- TB3_METAL_DENSITIES → metal-densities.json
- TB3_ENRICHMENT_MODELS → enrichment-models.json

Relative override paths must fail with a non-zero exit.
