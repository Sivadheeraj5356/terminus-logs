# ML training-signal contamination

wincontam is a machine-learning evaluation capability for chat-eval desks. It builds contamination-aware inference features from conversation timelines and scores deterministic eval metrics used as training-signal diagnostics before the next fine-tune cut.

## Training-gate role

Failed assistant turns that carry stale retrieval hashes, conflicting system-instruction versions, tool-artifact bleed, or repeated fact injections must not enter the supervised training feature batch as clean labels. Each scored `contam_rows` entry is one inference-time feature row; `contam_summary` and `session_scorecard` are the primary eval metric surfaces.

## Attribution lanes (process causes)

Process-cause precedence and clock rules live in `contam-attribution.md`. Severity rounding and needs_review thresholds live in `feature-eval-metric-contract.md`. Operator steps for absorb → score → emit live in `contam-eval-workflow.md`.

## Freeze-bound emission

Score seals the feature freeze and companion receipts. Emit must replay the sealed freeze payload after verifying digests — never rescore live manifests for the training cut.
