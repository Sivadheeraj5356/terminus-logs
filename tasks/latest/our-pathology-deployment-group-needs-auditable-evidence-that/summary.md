# Our pathology deployment group needs auditable evidence that one classifier beha

- **UUID:** `269bc9ec-18f2-4abb-9b46-fb49fcb27c1c`
- **Slug:** `our-pathology-deployment-group-needs-auditable-evidence-that`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Our pathology deployment group needs auditable evidence that one classifier behaves consistently when moved between DJL's PyTorch and ONNX Runtime engines. The Java trial workspace in `/app` is incomplete.

Retrieve the immutable model revision named in `/app/config/model-source.properties` with `/app/scripts/fetch_model.sh`; the paired weights are intentionally absent and their live Hugging Face download has no local substitute. Complete the evaluator under `/app/src/main/java` and build it with `/app/scripts/build.sh`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
