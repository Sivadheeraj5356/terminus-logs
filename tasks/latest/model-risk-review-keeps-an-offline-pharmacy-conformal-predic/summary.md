# Model risk review keeps an offline pharmacy conformal-prediction evaluator under

- **UUID:** `4ad8d490-d181-41b3-85d8-c387b4e282b6`
- **Slug:** `model-risk-review-keeps-an-offline-pharmacy-conformal-predic`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Model risk review keeps an offline pharmacy conformal-prediction evaluator under `/app/environment`. The evaluator scores pharmacy-ops uncertainty briefs under frozen conformal calibration annexes and must keep coverage behavior stable on held-out cross-border board pairs (adversarial generalization / out-of-distribution pairs).

Repair the sources under `/app/environment` so the evaluator can read the jurisdiction corpus, frozen conformal calibration runs under `/app/environment/data/cal/`, and the long-context board shards under `/app/environment/data/long_ctx/`, then write `/app/output/readiness_gonogo_brief.json`. That JSON must include gate_rows, rb_rows, seg_trace, and a 64-character lowercase hex brief_digest; each gate row carries clause_ids, seg_vec, disc_bind, and gate_kind; each rollback row carries metric_fam, bind_stamp, and hx_ref.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
