# Skirmish adjudicator

Offline hex battle resolver used by the local arena tooling.

Build and run via `/app/bin/skirmish`. The wrapper always rebuilds the release binary
from `/app/environment/skirmish` with `cargo build --release --locked`.

See `architecture.md` and `docs/` for module boundaries and coordinate notes.
Sample maps live under `data/maps/`; sample unit templates under `data/units/`.
