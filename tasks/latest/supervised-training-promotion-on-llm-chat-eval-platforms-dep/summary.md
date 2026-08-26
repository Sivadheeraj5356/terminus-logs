# Supervised training promotion on LLM chat-eval platforms depends on contaminatio

- **UUID:** `32790a15-9742-4b9f-a33e-b553d9650d7e`
- **Slug:** `supervised-training-promotion-on-llm-chat-eval-platforms-dep`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Supervised training promotion on LLM chat-eval platforms depends on contamination-aware inference features before failed assistant turns are admitted as clean supervision for the next fine-tune cut. Stale retrieval hashes, conflicting system-instruction versions, tool-artifact bleed, and repeated fact injections each leave different fingerprints on the turn timeline and distort training-signal eval metrics and inference feature batches.

Build the wincontam training-signal evaluator under /app as an ML eval capability that attributes contaminated failures from conversation manifests, scores per-session severity metrics, and seals a freeze-bound risk bulletin so later emission cannot silently rescore a mutated tree used as training features:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
