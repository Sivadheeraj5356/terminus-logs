# Single-molecule force spectroscopy watches one protein hop between its folded an

- **UUID:** `180fea04-64dd-4bb8-8419-2382dc6a9c48`
- **Slug:** `single-molecule-force-spectroscopy-watches-one-protein-hop-b`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Single-molecule force spectroscopy watches one protein hop between its folded and unfolded states while an optical trap holds it at a fixed load. Each hop is a diffusive crossing of the free-energy barrier, so the unfolding and folding rates measured at every load carry the shape of the landscape.

Two things sit in the way: each molecule's bead and linker geometry shifts its attempt frequency, and each trap calibration misreads the load it actually applied, so the force that enters the rate is not the force on the dial. Neither is observed and both differ from molecule to molecule.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
