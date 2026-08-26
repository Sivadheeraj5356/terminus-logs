# Quantum state-vector simulation under /app/wavefn_corpus drifted. Repair Go unde

- **UUID:** `a63ca930-e4cc-4bb3-88c9-8cf16a08ab93`
- **Slug:** `quantum-state-vector-simulation-under-app-wavefn-corpus-drif`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Quantum state-vector simulation under /app/wavefn_corpus drifted. Repair Go under /app, editing only qwavectl, ampstore, gatekron, circexec, numpolicy; leave wavefn_corpus, engine_spec, go.mod, Makefile unchanged.

Qubit zero is little-endian LSB. From /app, make build then make run writes /app/build/statevec_benchmark_report.json for forty-two roster circuits: compact JSON, byte-identical.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
