Supervised training promotion on LLM chat-eval platforms depends on contamination-aware inference features before failed assistant turns are admitted as clean supervision for the next fine-tune cut. Stale retrieval hashes, conflicting system-instruction versions, tool-artifact bleed, and repeated fact injections each leave different fingerprints on the turn timeline and distort training-signal eval metrics and inference feature batches.

Build the wincontam training-signal evaluator under /app as an ML eval capability that attributes contaminated failures from conversation manifests, scores per-session severity metrics, and seals a freeze-bound risk bulletin so later emission cannot silently rescore a mutated tree used as training features:

- absorb-context-hold records a corpus hold with corpus_stamp under --store.
- score-contam-window scores contaminated failures at --cutoff and --emitted-at, seals context_hold_freeze.json plus mutation_chain_receipt.json plus session_risk_ledger.json, and writes the live eval bulletin to --out.
- emit-risk-bulletin verifies those seals and emits the sealed freeze bulletin to --out without recomputing contamination from live manifests.

Manifests live under /app/data (or --corpus). Start from /app/docs/ml-training-signal-contamination.md and /app/docs/feature-eval-metric-contract.md; also follow /app/docs/contam-eval-workflow.md, /app/docs/contam-attribution.md, /app/docs/risk-bulletin-schema.md, /app/docs/context-hold-freeze.md, /app/docs/mutation-chain-receipt.md, /app/docs/session-risk-ledger.md, /app/docs/corpus-stamp.md, and /app/docs/sim-clock-turns.md.

Every bulletin field must derive from supplied manifests — never hardcoded session or turn identifiers. Last-occurrence-wins applies on duplicate primary keys. Identical corpus paths, --cutoff, and --emitted-at must produce byte-identical bulletins. wincontam::tokendiag::pairwise_overlap stays diagnostic-only and must not drive attribution or severity metrics.

Domain signals for this task: training-signal contamination, inference feature batches, eval metric severity, system-instruction conflict lanes, stale retrieval hash drift, tool-artifact bleed, repeated fact injection thresholds, residual contamination, freeze seals for feature cuts, mutation-chain attests, and session-risk ledgers. Do not borrow generic service-repair metaphors when attributing contaminated training turns.
