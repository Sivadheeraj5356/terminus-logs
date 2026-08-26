# A wildlife photographer is planning the next tour and has forty subjects lined u

- **UUID:** `55a3bdbe-2ac2-45c9-b10d-cb00799b5237`
- **Slug:** `a-wildlife-photographer-is-planning-the-next-tour-and-has-fo`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A wildlife photographer is planning the next tour and has forty subjects lined up to shoot, su-01 through su-40. Each one needs a frame budget going in: how many frames to spend from a shared public hide, and how many from a private guided sit.

The hide is the cheap route. It bills at `hide_cost` per frame but works off a single ration, `hide_frame_budget` frames to be split among all forty subjects, so once that ration is gone the rest of a subject's frames come from the guided route at the steeper `guide_cost`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
