# Scenario fixtures

Seq cases under `s0` through `s3` pair a xfer event snapshot (`a0.evt`), a
ledger snapshot (`b0.evt`), and a reservation fixture (`p0.res`).

- `a0.evt` carries `issue`, `source`, and `target` for the scenario.
- `b0.evt` carries ledger integers `stage`, `anchor`, and `settle`.
- `p0.res` carries `tail` and `epoch` for meter depth on backup-window runs.

`s0` is the frozen baseline. `s1` and `s2` exercise post-window barrier sequence.
`s3` is the backup-window case with extended meter sampling.
