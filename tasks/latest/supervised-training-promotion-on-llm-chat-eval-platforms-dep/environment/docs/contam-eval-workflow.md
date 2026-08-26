# Contamination eval workflow

Binary: `/app/target/release/wincontam`

## absorb-context-hold

```
wincontam absorb-context-hold --corpus <dir> --store <dir>
```

Writes `context_hold_snapshot.json` under `--store` with live `corpus_stamp` for the feature corpus.

## score-contam-window

```
wincontam score-contam-window --corpus <dir> --store <dir> --cutoff <ts> --emitted-at <ts> --out <path>
```

Requires a matching snapshot. Writes the contamination eval bulletin at `--out` and seals `context_hold_freeze.json`, `mutation_chain_receipt.json`, and `session_risk_ledger.json` under `--store`.

## emit-risk-bulletin

```
wincontam emit-risk-bulletin --corpus <dir> --store <dir> --cutoff <ts> --emitted-at <ts> --out <path>
```

Verifies freeze + mutation receipt + session risk ledger and emits the sealed freeze eval bulletin to `--out` without recomputing contamination from live manifests.

## Verifier note

Harnesses may set `TB3_CONTEXT_HOLD_PROBE` for hold probes. It does not change absorb, score, or emit semantics for eval metrics.
