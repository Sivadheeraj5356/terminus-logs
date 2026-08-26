# Trace lane profile

Multi-bundle trace runs in one interpreter must not reuse session-scoped compile state across unrelated bundles.

Each trace opens a fresh lane: genealogy blend coefficients and policy-family selection apply to the current bundle only. Catalog snapshots reload per trace; blend tables must not carry over from an earlier bundle with a different `policy_family`.

Dye restoration compiles through `shed_weave.tint_sequencer`, which orders snapshot clipping, school-recital gating, and multiplicative decay compounding. Dye events must be gated before compounding.

See `/app/docs/trace_phases.md` for the full phase order.
