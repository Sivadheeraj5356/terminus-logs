# Repair the pendulum motion solver

The `/app` pendulum imaging experiment stores short grayscale montages of a damped harmonic oscillator on a fixed capture cadence. The numerical reconstruction module is missing so natural frequency, exponential decay rate, per frame acceptance masks, and audit diagrams are absent or untrustworthy.

Repair the motion solver implementation in `/app` and fix any bundled `/app/environment/pendulum_recovery` modules the numerical pipeline depends on, using `/app/README.md` and `/app/schema.sql`. Implement `recover_motion.py` to decode each montage, track the bob center, reject noised or occluded frames, and fit the damped cosine model x(t)=A*exp(-gamma*t)*cos(2*pi*f*t+phi) with nonlinear least squares. Persist fitted f and gamma, accepted angle samples, per frame audit records, and Graphviz diagrams. Hand written parameter files or graph artifacts without running the solver will not pass verification.

Verification reruns `python3 recover_motion.py`, then `python3 /app/environment/pendulum_recovery/report.py`, and checks numerical outputs with pytest using the published relative tolerances.

Do not edit seeded montage inputs, `schema.sql`, `report.py`, or other shipped documentation. Do not hard code per capture frequencies, decay constants, or rejection indices.
