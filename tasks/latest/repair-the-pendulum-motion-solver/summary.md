# # Repair the pendulum motion solver

- **UUID:** `bb361b7b-e01f-4068-beac-4c197355eee7`
- **Slug:** `repair-the-pendulum-motion-solver`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The `/app` pendulum imaging experiment stores short grayscale montages of a damped harmonic oscillator on a fixed capture cadence. The numerical reconstruction module is missing so natural frequency, exponential decay rate, per frame acceptance masks, and audit diagrams are absent or untrustworthy.

Repair the motion solver implementation in `/app` and fix any bundled `/app/environment/pendulum_recovery` modules the numerical pipeline depends on, using `/app/README.md` and `/app/schema.sql`. Implement `recover_motion.py` to decode each montage, track the bob center, reject noised or occluded frames, and fit the damped cosine model x(t)=A*exp(-gamma*t)*cos(2*pi*f*t+phi) with nonlinear least squares.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
