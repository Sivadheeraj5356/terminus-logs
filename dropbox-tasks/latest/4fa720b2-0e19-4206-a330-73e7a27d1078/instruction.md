The Rust project in `/app` builds a binary called `cryoctl` that maintains a
per-cryostat boil-off warden for a bank of cryogenic helium storage vessels. It
reads a single JSON object from stdin describing a grace allowance and a stream
of timestamped events — cryostats crossing above and below their relief
threshold, transfer-line purge windows, and reports — replays them in order
against a continuous-time monitor, and writes one JSON object to stdout with an
`audit` trail, the closed `boiloff` intervals, and per-cryostat exposed
aggregates.

The current build handles the common case — a cryostat that dwells above its
relief threshold past the grace allowance and then settles — but mishandles how
the boil-off accrual interacts with transfer-line purge windows and with at-risk
stretches that cross the allowance between events, so some boil-off intervals and
exposed totals come out wrong. Fix the implementation so every case matches the
specification.

`/app/docs/spec.md` is the authoritative reference: it defines the exact input
and output formats, how the grace allowance is measured in active time, where a
boil-off interval's start and end instants fall, how a transfer-line purge window
pauses and later resumes the allowance clock, and which intervals are emitted.
Reproduce its behavior exactly while leaving the input and output formats
unchanged. The environment is offline; build with `/app/build.sh`, which leaves
the runnable binary at `/app/cryoctl`.
