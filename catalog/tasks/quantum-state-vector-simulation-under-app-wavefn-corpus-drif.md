# Quantum state-vector simulation under /app/wavefn_corpus drifted. Repair Go unde

Submission: `a63ca930-e4cc-4bb3-88c9-8cf16a08ab93`  
Slug: `quantum-state-vector-simulation-under-app-wavefn-corpus-drif`  
Latest archive: `a63ca930-e4cc-4bb3-88c9-8cf16a08ab93_submission_2026-07-16T04_53_01.728Z.zip`  
Revisions in Dropbox: 7

## Task summary

Quantum state-vector simulation under /app/wavefn_corpus drifted. Repair Go under /app, editing only qwavectl, ampstore, gatekron, circexec, numpolicy; leave wavefn_corpus, engine_spec, go.mod, Makefile unchanged. Qubit zero is little-endian LSB. From /app, make build then make run writes /app/build/statevec_benchmark_report.json for forty-two roster circuits: compact JSON, byte-identical. Norm, reverse_fidelity, re, and im are quoted ten-decimal JSON strings, never numbers, with positive-signed zeros. In main.go set corpusDir := "/app/wavefn_corpus", absolute report-path literal, and call pruneBuildStaging first. Follow /app/engine_spec/statevec_sim_contract.json. RX/RZ require theta; ignore decoy angle and qubit. CNOT/CZ/CPHASE control equal target, SWAP a equal b, and CSWAP repeated/out-of-range give QUBIT_OUT_OF_RANGE (cswap). CSWAP swaps a and b when control set. REWIND needs numeric depth: missing/null/negative gives UNKNOWN_GATE; zero no-ops; beyond history gives REWIND_OVERFLOW detail overflow. Unknown ops give UNKNOWN_GATE before range checks; structural stops keep reverse_fidelity 0.0000000000 and skip drift.

Required artifacts include: `/app/wavefn_corpus`, `/app/build/statevec_benchmark_report.json`, `/app/engine_spec/statevec_sim_contract.json`.

Author anonymous tagged this **hard** scientific-computing task (quantum-computing, state-vector, gate-simulation, numerical-methods, go).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `a63ca930-e4cc-4bb3-88c9-8cf16a08ab93_submission_2026-07-16T04_53_01.728Z.zip` is a task submission, not a Harbor job. 7 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
