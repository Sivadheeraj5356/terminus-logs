# Offline machine-learning evaluation of FlashAttention transformer inference: cal

- **UUID:** `9323bb30-2b2c-4857-aa46-4c8ba0fdeaa1`
- **Slug:** `offline-machine-learning-evaluation-of-flashattention-transf`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Offline machine-learning evaluation of FlashAttention transformer inference: calibrate Q/K/V tile geometry from the attention model profile at /app/config/attn-profile.json onto the paged KV-cache, track online-softmax logit features under the quantized sparse-mask graph from packs under /app/fixtures/public/, and grade the attention path into an offline residency seal. Keep the evaluator offline with no network listeners.

Deliverables are native ELF binaries at /app/bin/kvtile-plan, /app/bin/kvtile-advance, and /app/bin/kvtile-seal (not script wrappers). Normative contracts (required): /app/docs/behavior-register.md, /app/docs/tile-schedule-contract.md, /app/docs/online-softmax-contract.md, /app/docs/block-table-contract.md, /app/docs/sparse-mask-contract.md, /app/docs/residency-seal-schema.md, /app/docs/module-scope.md, /app/docs/cli-reference.md, /app/docs/runtime-env.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
