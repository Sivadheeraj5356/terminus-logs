# The LoRA merge evaluation lab under /app decides whether multi-adapter PEFT cand

- **UUID:** `7fcabcea-a975-4c20-8a9f-bdd23dadd8aa`
- **Slug:** `the-lora-merge-evaluation-lab-under-app-decides-whether-mult`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

The LoRA merge evaluation lab under /app decides whether multi-adapter PEFT candidates are safe to launch on a pinned base checkpoint. Score each launch candidate with /app/lora-gate <request-file> and publish the model-readiness board at /app/output/lora_merge_conflict_gate.json plus per-adapter findings at /app/output/adapter_findings.jsonl.

Requests use the existing line-oriented adapter/manifest interface documented by the source parser, including base checkpoint, revision, held-out evaluation parts, merge-risk limit, alias lines, and adapter leaf rows. The readiness board is a JSON object where request_id and model_view are strings, ready is boolean, score is an integer, and targets is an array of strings.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
