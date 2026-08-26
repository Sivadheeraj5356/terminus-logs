# Architecture

The adjudicator is a single Rust crate (`skirmish`) with a Bash entrypoint.

Layers:
- `parse` / `validate` — load scenario JSON and reject illegal placements
- `initiative` — turn order
- `engine` — action loop, MOVE / STRIKE / GUARD sequencing
- `hex` / `los` / `vision` / `beacon` — geometry and visibility
- `combat` / `overwatch` / `morale` — damage and interrupt effects
- `report` / `digest` — JSON transcript emission

Supporting trees under `data/`, `docs/`, `fixtures/`, and `tools/` hold
editorial notes and offline samples. They are not a second implementation.
