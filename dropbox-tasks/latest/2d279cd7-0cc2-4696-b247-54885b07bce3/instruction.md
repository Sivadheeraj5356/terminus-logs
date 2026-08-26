# Memory-Capped Wave Integrator

The Node integrator under `/app/` shows these symptoms in verifier workloads:

- Peak heap exceeds **15 MiB** during repeated 128×128 runs.
- Interior snapshots taken during integration **drift** when live arrays are overwritten after capture.
- Runs using the `mixed` halo profile become non-finite after roughly 200 steps.
- A 200-step uninterrupted reference stream **does not match** a 100-step run plus checkpoint resume for the same config.

The normal `run_entry.js` pipeline must regenerate traces from config; static or manual output writes are insufficient. Fix source code under `/app/` per the contract subsystem scope.

Observable contracts, checkpoint layout, CLI flags, and subsystem scope are in `/app/docs/pde_contract.md`. Write `/app/output_trace.json` with `gridSize`, `steps`, `stride`, `order`, `traces`, and `maxMemoryBytes` as defined there. Large workloads use `/app/run_capped.sh`, which enforces heap compliance externally.

```
node /app/run_entry.js <config.json> <output.json> [--checkpoint PATH] [--resume]
```

The verifier evaluates submissions with `pytest /tests/test_outputs.py`.
