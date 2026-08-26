# floating_point_numeric_policy

- **UUID:** `5d7231b2-e692-4b71-800b-eded87c740c0`
- **Slug:** `floating-point-numeric-policy`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

A seeded machine-learning training harness under `/app/environment` (Node) runs optimizer update loops with first/second moment accumulators and a learning-rate schedule over local fixture data, and supports halt-and-continue training. Resumed training must reproduce the same learning curves as an uninterrupted training run over the same inputs.

After a halt-and-continue cycle, `/app/output/stage` headline totals and `/app/environment/fixtures/interim/q3_hold.json` can look acceptable while the graded training audit still shows the resumed curve disagreeing with the uninterrupted curve for the same inputs. Update the training implementation under `/app/environment` so that a normal regeneration of the training audit outputs satisfies the public contracts.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
